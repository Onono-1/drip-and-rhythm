import type { Metadata } from "next";
import { cookies } from "next/headers";

import { InvitationSuccessClient } from "@/features/guest/invitation-success-client";
import { fetchServerJson } from "@/lib/server-api";
import type { ClaimReceiptPayload } from "@/types/api";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Invitation Secured",
  robots: { index: false, follow: false, nocache: true },
};

export default async function InvitationSuccessPage() {
  const cookieStore = await cookies();
  const receiptCookie = cookieStore.get("drip_claim_receipt")?.value;

  const res = receiptCookie
    ? await fetchServerJson<ClaimReceiptPayload>(
        "/api/claim-receipt/",
        `drip_claim_receipt=${encodeURIComponent(receiptCookie)}`,
      )
    : { ok: false, status: 401, data: null };

  return <InvitationSuccessClient initialReceipt={res.ok ? res.data : null} />;
}
