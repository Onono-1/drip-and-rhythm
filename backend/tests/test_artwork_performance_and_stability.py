from __future__ import annotations

import io
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import pytest
from django.test import override_settings
from PIL import Image
from rest_framework.test import APIClient

import apps.invitations.artwork as artwork_mod
from apps.accounts.models import User
from apps.communications.pdf_pass import build_qr_payload
from apps.invitations.artwork import FORMAT_SPECS, get_or_render_promotional_artwork
from apps.invitations.crypto import decrypt_token
from apps.invitations.services import claim_invitation, generate_invitations, revoke_invitation


@pytest.mark.django_db(transaction=True)
def test_artwork_formats_caching_coalescing_privacy_revocation_and_admission_priority(tmp_path):
    with override_settings(ARTWORK_CACHE_DIR=str(tmp_path)):
        super_admin = User.objects.create_superuser(
            email="perf-admin@drip.test",
            password="StrongPerfPassword!2026",
            display_name="Chief Host",
        )
        batch = generate_invitations(actor=super_admin, quantity=3)
        tok1 = batch.invitations[0][1].rsplit("/invite/", 1)[1]
        tok2 = batch.invitations[1][1].rsplit("/invite/", 1)[1]
        tok3 = batch.invitations[2][1].rsplit("/invite/", 1)[1]

        c1 = claim_invitation(raw_token=tok1, raw_nickname="Zuri", raw_email="zuri-p@example.com", raw_gender="FEMALE")
        c2 = claim_invitation(raw_token=tok2, raw_nickname="Musa", raw_email="musa-p@example.com", raw_gender="MALE")
        c3 = claim_invitation(raw_token=tok3, raw_nickname="Nia", raw_email="nia-p@example.com", raw_gender="FEMALE")

        event = c1.invitation.event

        # 1. All 4 formats generate exact dimensions + cached repeat is instant
        timings: dict[str, tuple[float, float]] = {}
        for fmt, expected_size in FORMAT_SPECS.items():
            t0 = time.perf_counter()
            res_cold = get_or_render_promotional_artwork(
                event=event,
                format_name=fmt,
                nickname=c1.invitation.nickname,
                show_nickname=False,
                invitation_id=str(c1.invitation.id),
                sharing_version=c1.invitation.sharing_version,
            )
            cold_ms = (time.perf_counter() - t0) * 1000.0
            assert res_cold.cache_hit is False
            with Image.open(io.BytesIO(res_cold.png_bytes)) as im:
                assert im.size == expected_size

            t1 = time.perf_counter()
            res_warm = get_or_render_promotional_artwork(
                event=event,
                format_name=fmt,
                nickname=c1.invitation.nickname,
                show_nickname=False,
                invitation_id=str(c1.invitation.id),
                sharing_version=c1.invitation.sharing_version,
            )
            warm_ms = (time.perf_counter() - t1) * 1000.0
            assert res_warm.cache_hit is True
            assert res_warm.png_bytes == res_cold.png_bytes
            timings[fmt] = (cold_ms, warm_ms)

        print("OBSERVED_ARTWORK_TIMINGS_MS:", {k: (round(v[0], 1), round(v[1], 2)) for k, v in timings.items()})

        # 2. Second guest with anonymous mode reuses shared anonymous cache without rendering
        with patch.object(artwork_mod, "_render_png_bytes_uncached", wraps=artwork_mod._render_png_bytes_uncached) as spy:
            res_guest2 = get_or_render_promotional_artwork(
                event=event,
                format_name="story",
                nickname=c2.invitation.nickname,
                show_nickname=False,
                invitation_id=str(c2.invitation.id),
                sharing_version=c2.invitation.sharing_version,
            )
            assert res_guest2.cache_hit is True
            assert spy.call_count == 0

        # 3. Concurrent identical personalized requests coalesce into a SINGLE render
        c1.invitation.show_nickname_publicly = True
        c1.invitation.sharing_version += 1
        c1.invitation.save(update_fields=["show_nickname_publicly", "sharing_version", "updated_at"])

        orig_render = artwork_mod._render_png_bytes_uncached
        render_calls = 0
        call_lock = threading.Lock()

        def _counted_render(ev, fmt, nick):
            nonlocal render_calls
            with call_lock:
                render_calls += 1
            time.sleep(0.15)
            return orig_render(ev, fmt, nick)

        with patch.object(artwork_mod, "_render_png_bytes_uncached", side_effect=_counted_render):
            with ThreadPoolExecutor(max_workers=4) as pool:
                futs = [
                    pool.submit(
                        get_or_render_promotional_artwork,
                        event=event,
                        format_name="story",
                        nickname=c1.invitation.nickname,
                        show_nickname=True,
                        invitation_id=str(c1.invitation.id),
                        sharing_version=c1.invitation.sharing_version,
                    )
                    for _ in range(4)
                ]
                results = [f.result() for f in futs]
            assert render_calls == 1
            assert len({r.png_bytes for r in results}) == 1

        # 4. HTTP ETag / download / revocation / sharing-disabled checks BEFORE serving cache
        anon_client = APIClient()
        img_url = f"/api/share/{c1.raw_share_token}/image/?format=story&v={c1.invitation.sharing_version}"
        r_ok = anon_client.get(img_url)
        assert r_ok.status_code == 200
        assert r_ok["Content-Type"] == "image/png"
        etag = r_ok["ETag"]

        r_304 = anon_client.get(img_url, HTTP_IF_NONE_MATCH=etag)
        assert r_304.status_code == 304

        r_dl = anon_client.get(f"{img_url}&download=1")
        assert r_dl.status_code == 200
        assert 'filename="drip-and-rhythm-story.png"' in r_dl["Content-Disposition"]

        # Disabling public sharing immediately blocks cached access (including ETag revalidation)
        c1.invitation.public_sharing_enabled = False
        c1.invitation.save(update_fields=["public_sharing_enabled", "updated_at"])
        assert anon_client.get(img_url).status_code == 404
        assert anon_client.get(img_url, HTTP_IF_NONE_MATCH=etag).status_code == 404

        # Revocation also blocks cached access
        revoke_invitation(actor=super_admin, invitation_id=c2.invitation.id, reason="Test revoke")
        assert anon_client.get(f"/api/share/{c2.raw_share_token}/image/?format=story").status_code == 404

        # 5. Capacity gate & admission priority: while render slot is occupied, second uncached
        # artwork gets 503 + Retry-After, while /api/health/, QR /api/verify/ & /api/check-in/ stay fast
        c3.invitation.show_nickname_publicly = True
        c3.invitation.sharing_version += 1
        c3.invitation.save(update_fields=["show_nickname_publicly", "sharing_version", "updated_at"])

        admin_client = APIClient()
        admin_client.force_authenticate(user=super_admin)
        raw_adm_token = decrypt_token(c3.invitation.admission_token_encrypted)
        qr_payload = build_qr_payload(raw_adm_token)

        # Acquire the single artwork render slot to simulate an active heavy render
        acquired = artwork_mod._RENDER_SEMAPHORE.acquire(blocking=False)
        assert acquired is True
        try:
            with patch.object(artwork_mod, "RENDER_ACQUIRE_TIMEOUT_SECONDS", 0.05):
                busy_resp = anon_client.get(
                    f"/api/share/{c3.raw_share_token}/image/?format=square&v={c3.invitation.sharing_version}"
                )
                assert busy_resp.status_code == 503
                assert busy_resp["Retry-After"] == "3"

                t_crit = time.perf_counter()
                health_resp = anon_client.get("/api/health/")
                verify_resp = admin_client.post("/api/verify/", {"qr_payload": qr_payload}, format="json")
                admit_resp = admin_client.post(
                    "/api/check-in/",
                    {"verification_method": "QR", "qr_payload": qr_payload},
                    format="json",
                )
                crit_ms = (time.perf_counter() - t_crit) * 1000.0
                assert health_resp.status_code == 200
                assert verify_resp.status_code == 200
                assert verify_resp.json()["can_admit"] is True
                assert admit_resp.status_code == 201
                print("OBSERVED_CRITICAL_OPS_DURING_RENDER_MS:", round(crit_ms, 1))
        finally:
            artwork_mod._RENDER_SEMAPHORE.release()
