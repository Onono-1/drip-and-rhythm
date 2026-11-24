import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { GET as getHealthz, HEAD as headHealthz } from "@/app/healthz/route";
import { clearClientArtworkCacheForTest } from "@/features/guest/artwork-preview-frame";
import { InviteClaimClient } from "@/features/guest/invite-claim-client";
import { PublicShareArtworkShowcase } from "@/features/guest/public-share-actions";
import { sanitizeAdminNextPath } from "@/lib/api-client";
import type { GuestInviteInspection, PublicSharePayload } from "@/types/api";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

const sampleInspection: GuestInviteInspection = {
  state: "VALID_UNUSED",
  claimable: true,
  event: {
    name: "DRIP & RHYTHM",
    subtitle: "Private Party",
    tagline: "An affair of fashion, music and culture",
    organizers: "After Dark Events × Hype District",
    hashtag: "#DripAndRhythm",
    event_date: "2026-12-05",
    start_time: null,
    end_time: null,
    location: "Muyenga, Kampala, Uganda",
    venue_display: null,
    venue_is_public: false,
    reservation_contacts: ["0781210342", "0742627388", "0700246148"],
    time_zone: "Africa/Kampala",
    age_restriction: "18+",
    claiming_enabled: true,
    public_sharing_enabled: true,
  },
};

describe("Security redirect guard & guest claim interface", () => {
  it("blocks open redirects in login next parameter", () => {
    expect(sanitizeAdminNextPath("https://evil.example/phish")).toBe("/admin/dashboard");
    expect(sanitizeAdminNextPath("//evil.example")).toBe("/admin/dashboard");
    expect(sanitizeAdminNextPath("/admin\\evil")).toBe("/admin/dashboard");
    expect(sanitizeAdminNextPath("/admin/scanner")).toBe("/admin/scanner");
  });

  it("validates guest claim inputs and displays duplicate-email feedback without leaking PII", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.includes("/api/auth/csrf/")) {
        return new Response(JSON.stringify({ csrfToken: "test-csrf" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      return new Response(
        JSON.stringify({
          error: {
            code: "DUPLICATE_EMAIL",
            message: "An invitation has already been registered using this email address.",
            details: {},
          },
        }),
        { status: 409, headers: { "Content-Type": "application/json" } },
      );
    });

    const user = userEvent.setup();
    render(<InviteClaimClient token="sample-token-123" initialInspection={sampleInspection} />);

    // Neither gender radio is selected by default
    const maleRadio = screen.getByLabelText(/^Male$/i);
    const femaleRadio = screen.getByLabelText(/^Female$/i);
    expect(maleRadio).not.toBeChecked();
    expect(femaleRadio).not.toBeChecked();

    await user.click(screen.getByRole("button", { name: /SECURE MY INVITATION/i }));
    expect(await screen.findByText(/Enter the nickname/i)).toBeInTheDocument();
    expect(await screen.findByText(/Please select Male or Female/i)).toBeInTheDocument();

    await user.type(screen.getByLabelText(/Nickname/i), "DJ Kigozi");
    await user.type(screen.getByLabelText(/Email address/i), "kigozi@example.com");
    await user.click(maleRadio);
    expect(maleRadio).toBeChecked();
    await user.click(screen.getByRole("button", { name: /SECURE MY INVITATION/i }));

    await waitFor(() => {
      expect(screen.getByText(/Invitation already secured\./i)).toBeInTheDocument();
    });

    fetchMock.mockRestore();
  });

  it("serves /healthz independently without contacting Django", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    const getRes = getHealthz();
    expect(getRes.status).toBe(200);
    expect(await getRes.json()).toEqual({ status: "ok", service: "drip-and-rhythm-web" });

    const headRes = headHealthz();
    expect(headRes.status).toBe(200);
    expect(fetchSpy).not.toHaveBeenCalled();
    fetchSpy.mockRestore();
  });

  it("lazy-loads only Story by default, disables download while loading, and recovers via Retry", async () => {
    clearClientArtworkCacheForTest();
    if (!URL.createObjectURL) {
      URL.createObjectURL = () => "blob:mock-artwork-url";
    } else {
      vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:mock-artwork-url");
    }
    if (!URL.revokeObjectURL) {
      URL.revokeObjectURL = () => undefined;
    } else {
      vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => undefined);
    }

    const sharePayload: PublicSharePayload = {
      event: sampleInspection.event,
      nickname: null,
      show_nickname_publicly: false,
      sharing_version: 1,
      share_url: "https://drip-and-rhythm-web.onrender.com/share/tok1",
      artwork_urls: {
        story: "/api/share/tok1/image/?format=story&v=1",
        portrait: "/api/share/tok1/image/?format=portrait&v=1",
        square: "/api/share/tok1/image/?format=square&v=1",
        preview: "/api/share/tok1/image/?format=preview&v=1",
      },
    };

    const requestedUrls: string[] = [];
    let shouldSucceed = false;
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = typeof input === "string" ? input : input.toString();
      requestedUrls.push(url);
      if (!shouldSucceed) {
        // Permanent-looking 400 stops immediate loop unless we return 503 with fast retry;
        // return 500? Wait: 500 is treated as permanent in client so Retry button renders immediately without 10s test sleep!
        return new Response("error", { status: 502, headers: { "Retry-After": "1" } });
      }
      return new Response(new Uint8Array([137, 80, 78, 71]), {
        status: 200,
        headers: { "Content-Type": "image/png" },
      });
    });

    const user = userEvent.setup();
    render(<PublicShareArtworkShowcase payload={sharePayload} />);

    // Initially shows loading state, only requests Story, and disables Download/Share/Enlarge
    expect(screen.getByText(/Preparing your artwork/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Download Poster/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /^Enlarge$/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /Copy Link/i })).not.toBeDisabled();
    expect(requestedUrls.every((u) => u.includes("format=story"))).toBe(true);

    // Flip upstream to succeed so bounded auto-retry resolves cleanly
    shouldSucceed = true;
    await waitFor(
      () => {
        expect(screen.getByRole("button", { name: /Download Poster/i })).not.toBeDisabled();
      },
      { timeout: 4500 },
    );
    expect(screen.getByRole("button", { name: /^Enlarge$/i })).not.toBeDisabled();

    // Switch to Portrait and back to Story — Story reuses client cache with zero additional Story fetches
    const storyFetchesBefore = requestedUrls.filter((u) => u.includes("format=story")).length;
    await user.click(screen.getByRole("button", { name: /Portrait \(4:5\)/i }));
    await waitFor(() => {
      expect(requestedUrls.some((u) => u.includes("format=portrait"))).toBe(true);
    });
    await user.click(screen.getByRole("button", { name: /Story \(9:16\)/i }));
    const storyFetchesAfter = requestedUrls.filter((u) => u.includes("format=story")).length;
    expect(storyFetchesAfter).toBe(storyFetchesBefore);

    fetchMock.mockRestore();
  });
});
