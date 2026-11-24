import type { Metadata } from "next";

import { InviteClaimClient } from "@/features/guest/invite-claim-client";
import { fetchPublicEventServer, fetchServerJson } from "@/lib/server-api";
import type { GuestInviteInspection } from "@/types/api";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Exclusive Invitation",
  robots: { index: false, follow: false, nocache: true },
};

export default async function GuestInvitePage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = await params;
  const res = await fetchServerJson<GuestInviteInspection>(
    `/api/invite/${encodeURIComponent(token)}/`,
  );

  const inspection: GuestInviteInspection =
    res.ok && res.data
      ? res.data
      : {
          state: "INVALID_INVITATION",
          claimable: false,
          event: await fetchPublicEventServer(),
        };

  return <InviteClaimClient token={token} initialInspection={inspection} />;
}
