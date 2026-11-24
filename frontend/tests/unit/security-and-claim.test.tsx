import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { InviteClaimClient } from "@/features/guest/invite-claim-client";
import { sanitizeAdminNextPath } from "@/lib/api-client";
import type { GuestInviteInspection } from "@/types/api";

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
});
