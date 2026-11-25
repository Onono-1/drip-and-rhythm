"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { AlertCircle, CheckCircle2, Lock, Mail, ShieldAlert } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { OrganizerWordmark } from "@/components/brand/organizer-wordmark";
import { WhatsAppContactLinks } from "@/components/brand/whatsapp-contacts";
import { Button, Input } from "@/components/ui/primitives";
import { ApiClientError, apiFetch, ensureCsrfToken, formatEventDate } from "@/lib/api-client";
import type { ClaimReceiptPayload, GuestInviteInspection, GuestInviteState } from "@/types/api";

const claimSchema = z.object({
  nickname: z
    .string()
    .trim()
    .min(1, "Enter the nickname you want on your invitation.")
    .max(50, "Nickname must be 50 characters or fewer.")
    .refine((v) => !/[<>]/.test(v), "HTML brackets are not permitted in nicknames."),
  email: z
    .string()
    .trim()
    .min(1, "Enter your email address to receive your PDF pass.")
    .email("Enter a valid email address."),
  gender: z.enum(["MALE", "FEMALE"], {
    message: "Please select Male or Female.",
  }),
});

type ClaimFormValues = z.infer<typeof claimSchema>;

export function InviteClaimClient({
  token,
  initialInspection,
}: {
  token: string;
  initialInspection: GuestInviteInspection;
}) {
  const router = useRouter();
  const [inviteState, setInviteState] = useState<GuestInviteState>(initialInspection.state);
  const [duplicateEmailNotice, setDuplicateEmailNotice] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [isClaiming, setIsClaiming] = useState(false);
  const { event } = initialInspection;

  useEffect(() => {
    void ensureCsrfToken();
  }, []);

  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<ClaimFormValues>({
    resolver: zodResolver(claimSchema),
    defaultValues: { nickname: "", email: "" },
  });

  const onSubmit = async (values: ClaimFormValues) => {
    if (isClaiming) return;
    setIsClaiming(true);
    setFormError(null);
    setDuplicateEmailNotice(false);

    try {
      await apiFetch<ClaimReceiptPayload>(`/api/invite/${encodeURIComponent(token)}/claim/`, {
        method: "POST",
        json: values,
      });
      router.push("/invitation/success");
    } catch (err) {
      if (err instanceof ApiClientError) {
        if (err.code === "DUPLICATE_EMAIL") {
          setDuplicateEmailNotice(true);
          return;
        }
        if (
          err.code === "INVITATION_ALREADY_CLAIMED" ||
          err.code === "INVITATION_EXPIRED" ||
          err.code === "INVITATION_REVOKED" ||
          err.code === "INVALID_INVITATION" ||
          err.code === "CLAIMING_DISABLED" ||
          err.code === "MASTER_LINK_EXHAUSTED" ||
          err.code === "MASTER_LINK_PAUSED" ||
          err.code === "MASTER_LINK_CLOSED"
        ) {
          setInviteState(err.code);
          return;
        }
        if (err.code === "VALIDATION_ERROR") {
          const nickErr = err.details.nickname;
          const emailErr = err.details.email;
          const genderErr = err.details.gender;
          if (Array.isArray(nickErr) && nickErr[0]) {
            setError("nickname", { message: String(nickErr[0]) });
          }
          if (Array.isArray(emailErr) && emailErr[0]) {
            setError("email", { message: String(emailErr[0]) });
          }
          if (Array.isArray(genderErr) && genderErr[0]) {
            setError("gender", { message: String(genderErr[0]) });
          }
        }
        setFormError(err.message);
      } else {
        setFormError("Unable to complete your claim right now. Check your connection and try again.");
      }
    } finally {
      setIsClaiming(false);
    }
  };

  const formattedDate = formatEventDate(event.event_date);

  return (
    <div className="amber-stage-glow film-grain flex min-h-dvh flex-col justify-between">
      <header className="border-b border-champagne/15 bg-midnight/90">
        <div className="mx-auto flex max-w-4xl items-center justify-between px-5 py-4 sm:px-8">
          <Link href="/">
            <OrganizerWordmark organizers={event.organizers} />
          </Link>
          <span className="rounded border border-crimson/70 bg-crimson/25 px-2.5 py-1 text-[11px] font-bold text-ivory">
            {event.age_restriction}
          </span>
        </div>
      </header>

      <main id="main-content" className="mx-auto w-full max-w-xl px-5 py-10 sm:px-8 sm:py-14">
        {inviteState === "VALID_UNUSED" ? (
          <div className="rounded-lg border border-champagne/35 bg-espresso/95 p-6 shadow-[0_20px_60px_rgba(0,0,0,0.55)] sm:p-9">
            <div className="flex items-center gap-3.5">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src="/branding/event-poster.jpeg"
                alt="DRIP & RHYTHM"
                width={64}
                height={64}
                className="h-16 w-16 shrink-0 rounded border border-amber/40 object-cover"
              />
              <div>
                <p className="font-script text-2xl leading-none text-amber">{event.subtitle}</p>
                <p className="font-display text-2xl tracking-wide text-ivory uppercase">{event.name}</p>
                <p className="text-xs text-champagne">
                  {formattedDate} · {event.location}
                </p>
              </div>
            </div>

            <hr className="my-6 border-champagne/20" />

            <h1 className="font-display text-4xl tracking-wide text-ivory uppercase sm:text-5xl">
              YOU&apos;RE ON THE LIST.
            </h1>
            <p className="mt-2 text-sm leading-relaxed text-ivory-muted">
              Enter your details to secure your exclusive invitation to {event.name}. Your official PDF admission pass will be sent directly to your email.
            </p>

            {duplicateEmailNotice && (
              <div
                role="alert"
                className="mt-6 rounded-md border border-amber/50 bg-chocolate/80 p-4 text-sm text-ivory"
              >
                <div className="flex items-start gap-3">
                  <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-amber" aria-hidden="true" />
                  <div>
                    <p className="font-bold text-amber">Invitation already secured.</p>
                    <p className="mt-1 leading-relaxed text-ivory/90">
                      An invitation has already been registered using this email address. Please check your inbox or spam folder for your official admission pass.
                    </p>
                  </div>
                </div>
              </div>
            )}

            {formError && (
              <div
                role="alert"
                className="mt-6 flex items-start gap-3 rounded-md border border-status-err/50 bg-red-950/60 p-4 text-sm text-red-100"
              >
                <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-status-err" aria-hidden="true" />
                <span>{formError}</span>
              </div>
            )}

            <form onSubmit={handleSubmit(onSubmit)} noValidate className="mt-6 space-y-5">
              <div>
                <label htmlFor="guest-nickname" className="block text-sm font-semibold text-champagne">
                  Nickname
                </label>
                <Input
                  id="guest-nickname"
                  type="text"
                  autoComplete="nickname"
                  placeholder="What do people call you?"
                  error={errors.nickname?.message}
                  className="mt-1.5"
                  {...register("nickname")}
                />
                {errors.nickname && (
                  <p role="alert" className="mt-1.5 text-xs font-medium text-status-err">
                    {errors.nickname.message}
                  </p>
                )}
              </div>

              <div>
                <label htmlFor="guest-email" className="block text-sm font-semibold text-champagne">
                  Email address
                </label>
                <Input
                  id="guest-email"
                  type="email"
                  autoComplete="email"
                  placeholder="you@example.com"
                  error={errors.email?.message}
                  className="mt-1.5"
                  {...register("email")}
                />
                {errors.email && (
                  <p role="alert" className="mt-1.5 text-xs font-medium text-status-err">
                    {errors.email.message}
                  </p>
                )}
              </div>

              <fieldset>
                <legend className="block text-sm font-semibold text-champagne">Gender</legend>
                <div className="mt-1.5 grid grid-cols-2 gap-3">
                  {(
                    [
                      { value: "MALE", label: "Male" },
                      { value: "FEMALE", label: "Female" },
                    ] as const
                  ).map((option) => (
                    <label
                      key={option.value}
                      className={`flex min-h-12 cursor-pointer items-center gap-3 rounded-md border px-4 py-2.5 text-sm font-medium text-ivory transition-colors duration-150 has-[:checked]:border-amber has-[:checked]:bg-chocolate/70 has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-amber ${
                        errors.gender
                          ? "border-status-err/70 bg-midnight/85"
                          : "border-champagne/25 bg-midnight/85 hover:border-champagne/50"
                      }`}
                    >
                      <input
                        type="radio"
                        value={option.value}
                        className="h-4 w-4 shrink-0 accent-burnt"
                        {...register("gender")}
                      />
                      <span>{option.label}</span>
                    </label>
                  ))}
                </div>
                {errors.gender && (
                  <p role="alert" className="mt-1.5 text-xs font-medium text-status-err">
                    {errors.gender.message}
                  </p>
                )}
              </fieldset>

              <Button
                type="submit"
                size="lg"
                loading={isSubmitting || isClaiming}
                disabled={isSubmitting || isClaiming}
                className="w-full"
              >
                SECURE MY INVITATION
              </Button>
            </form>

            <div className="mt-6 space-y-2 border-t border-champagne/15 pt-4 text-xs leading-relaxed text-ivory-muted">
              <p className="flex items-center gap-2">
                <Lock className="h-3.5 w-3.5 shrink-0 text-amber" aria-hidden="true" />
                <span>Single-use invitation link · Admits one guest only ({event.age_restriction}).</span>
              </p>
              <p className="flex items-center gap-2">
                <Mail className="h-3.5 w-3.5 shrink-0 text-amber" aria-hidden="true" />
                <span>
                  Your nickname appears on your promotional artwork and public sharing page; your email and gender stay private.{" "}
                  <Link href="/privacy" className="text-champagne underline hover:text-ivory">
                    Privacy notice
                  </Link>
                </span>
              </p>
            </div>
          </div>
        ) : (
          <NonClaimableStateCard state={inviteState} event={event} />
        )}
      </main>

      <footer className="border-t border-champagne/15 px-5 py-6 text-center text-xs text-ivory-muted">
        <p>
          {event.name} · {formattedDate} · {event.location}
        </p>
        {event.reservation_contacts.length > 0 && (
          <div className="mt-3 flex flex-col items-center gap-1.5">
            <span className="text-[11px] text-champagne">Need assistance? Message the host desk on WhatsApp:</span>
            <WhatsAppContactLinks event={event} variant="inline" />
          </div>
        )}
      </footer>
    </div>
  );
}

function NonClaimableStateCard({
  state,
  event,
}: {
  state: Exclude<GuestInviteState, "VALID_UNUSED">;
  event: GuestInviteInspection["event"];
}) {
  const copyMap: Record<
    Exclude<GuestInviteState, "VALID_UNUSED">,
    { title: string; body: string }
  > = {
    INVITATION_ALREADY_CLAIMED: {
      title: "INVITATION ALREADY CLAIMED",
      body: "This single-use invitation link has already been claimed. If you claimed it earlier, check your email inbox or spam folder for your attached PDF admission pass.",
    },
    INVITATION_EXPIRED: {
      title: "INVITATION EXPIRED",
      body: "The claim window for this invitation link has passed. Reach out to your event host if you need a replacement invitation.",
    },
    INVITATION_REVOKED: {
      title: "INVITATION UNAVAILABLE",
      body: "This invitation link has been deactivated by the event organizers and can no longer be used.",
    },
    CLAIMING_DISABLED: {
      title: "CLAIMING PAUSED",
      body: "Guest invitation claiming is currently closed. Please check back shortly or contact the organizers.",
    },
    INVALID_INVITATION: {
      title: "UNRECOGNIZED INVITATION LINK",
      body: "We could not match this URL to a valid DRIP & RHYTHM invitation. Verify that the full link shared with you was copied without missing characters.",
    },
    MASTER_LINK_EXHAUSTED: {
      title: "ALLOCATION FULLY CLAIMED",
      body: "All invitations allocated to this link have been claimed. If you already secured your spot, check your email inbox or spam folder for your PDF admission pass.",
    },
    MASTER_LINK_PAUSED: {
      title: "INVITATION LINK PAUSED",
      body: "Claims through this invitation link are temporarily paused by the organizers. Please check back later or contact the host desk for assistance.",
    },
    MASTER_LINK_CLOSED: {
      title: "INVITATION LINK CLOSED",
      body: "This invitation link has been closed by the event organizers and is no longer accepting new claims. Already issued passes remain valid.",
    },
  };

  const content = copyMap[state];

  return (
    <div className="rounded-lg border border-champagne/30 bg-espresso/95 p-7 text-center sm:p-10">
      <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full border border-amber/40 bg-chocolate text-amber">
        <ShieldAlert className="h-6 w-6" aria-hidden="true" />
      </div>
      <h1 className="font-display mt-5 text-3xl tracking-wide text-ivory uppercase sm:text-4xl">
        {content.title}
      </h1>
      <p className="mt-3 text-sm leading-relaxed text-ivory-muted sm:text-base">{content.body}</p>
      {event.reservation_contacts.length > 0 && (
        <div className="mt-6 space-y-2">
          <p className="text-xs font-medium text-champagne">Host Desk (WhatsApp):</p>
          <WhatsAppContactLinks event={event} variant="pills" />
        </div>
      )}
      <div className="mt-7">
        <Link href="/">
          <Button variant="outline">View Event Homepage</Button>
        </Link>
      </div>
    </div>
  );
}
