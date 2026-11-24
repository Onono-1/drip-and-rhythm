"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Save } from "lucide-react";
import { useState, type FormEvent } from "react";

import { Button, Input } from "@/components/ui/primitives";
import { AdminGuardShell } from "@/features/admin/admin-shell";
import { ApiClientError, apiFetch } from "@/lib/api-client";
import type { AdminEventSettings } from "@/types/api";

function SettingsForm({ settings }: { settings: AdminEventSettings }) {
  const queryClient = useQueryClient();

  const [name, setName] = useState(settings.name);
  const [tagline, setTagline] = useState(settings.tagline);
  const [eventDate, setEventDate] = useState(settings.event_date);
  const [startTime, setStartTime] = useState(settings.start_time ? settings.start_time.slice(0, 5) : "");
  const [endTime, setEndTime] = useState(settings.end_time ? settings.end_time.slice(0, 5) : "");
  const [location, setLocation] = useState(settings.location);
  const [exactVenue, setExactVenue] = useState(settings.exact_venue);
  const [venuePublic, setVenuePublic] = useState(settings.venue_is_public);
  const [contactsStr, setContactsStr] = useState(settings.reservation_contacts.join(", "));
  const [globalLimitStr, setGlobalLimitStr] = useState(
    settings.global_invitation_limit !== null ? String(settings.global_invitation_limit) : "",
  );
  const [maxBulk, setMaxBulk] = useState(settings.max_bulk_quantity);
  const [claimingEnabled, setClaimingEnabled] = useState(settings.claiming_enabled);
  const [admissionEnabled, setAdmissionEnabled] = useState(settings.admission_enabled);
  const [publicSharingEnabled, setPublicSharingEnabled] = useState(settings.public_sharing_enabled);

  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState<{ type: "ok" | "err"; text: string } | null>(null);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setFeedback(null);
    try {
      const contacts = contactsStr
        .split(",")
        .map((c) => c.trim())
        .filter(Boolean);

      await apiFetch("/api/event/settings/", {
        method: "PATCH",
        json: {
          name: name.trim(),
          tagline: tagline.trim(),
          event_date: eventDate,
          start_time: startTime || null,
          end_time: endTime || null,
          location: location.trim(),
          exact_venue: exactVenue.trim(),
          venue_is_public: venuePublic,
          reservation_contacts: contacts,
          global_invitation_limit: globalLimitStr.trim() === "" ? null : Number(globalLimitStr),
          max_bulk_quantity: maxBulk,
          claiming_enabled: claimingEnabled,
          admission_enabled: admissionEnabled,
          public_sharing_enabled: publicSharingEnabled,
        },
      });
      await queryClient.invalidateQueries({ queryKey: ["admin-event-settings"] });
      await queryClient.invalidateQueries({ queryKey: ["admin-dashboard"] });
      setFeedback({ type: "ok", text: "Saved event configuration." });
    } catch (err) {
      setFeedback({
        type: "err",
        text: err instanceof ApiClientError ? err.message : "Failed to save settings.",
      });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="max-w-4xl space-y-6">
      <div className="border-b border-champagne/15 pb-5">
        <h1 className="font-display text-4xl tracking-wide text-ivory uppercase">EVENT SETTINGS</h1>
        <p className="mt-1 text-sm text-ivory-muted">
          Configure event schedule, venue disclosure, global capacity, and live operational switches.
        </p>
      </div>

      {feedback && (
        <div
          role="status"
          className={`rounded border p-4 text-sm ${
            feedback.type === "ok"
              ? "border-emerald-500/40 bg-emerald-950/60 text-emerald-100"
              : "border-status-err/50 bg-red-950/60 text-red-100"
          }`}
        >
          {feedback.text}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6 rounded-lg border border-champagne/20 bg-espresso p-6 sm:p-8">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <label htmlFor="ev-name" className="block text-sm font-semibold text-champagne">
              Event name
            </label>
            <Input
              id="ev-name"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="mt-1.5"
            />
          </div>
          <div>
            <label htmlFor="ev-date" className="block text-sm font-semibold text-champagne">
              Event date
            </label>
            <Input
              id="ev-date"
              type="date"
              required
              value={eventDate}
              onChange={(e) => setEventDate(e.target.value)}
              className="mt-1.5"
            />
          </div>
        </div>

        <div>
          <label htmlFor="ev-tagline" className="block text-sm font-semibold text-champagne">
            Tagline
          </label>
          <Input
            id="ev-tagline"
            required
            value={tagline}
            onChange={(e) => setTagline(e.target.value)}
            className="mt-1.5"
          />
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <label htmlFor="ev-start" className="block text-sm font-semibold text-champagne">
              Starting time (optional until confirmed)
            </label>
            <Input
              id="ev-start"
              type="time"
              value={startTime}
              onChange={(e) => setStartTime(e.target.value)}
              className="mt-1.5"
            />
          </div>
          <div>
            <label htmlFor="ev-end" className="block text-sm font-semibold text-champagne">
              Ending time (optional)
            </label>
            <Input
              id="ev-end"
              type="time"
              value={endTime}
              onChange={(e) => setEndTime(e.target.value)}
              className="mt-1.5"
            />
          </div>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <label htmlFor="ev-loc" className="block text-sm font-semibold text-champagne">
              District / Location
            </label>
            <Input
              id="ev-loc"
              required
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              className="mt-1.5"
            />
          </div>
          <div>
            <label htmlFor="ev-venue" className="block text-sm font-semibold text-champagne">
              Exact venue (included on official PDF pass)
            </label>
            <Input
              id="ev-venue"
              value={exactVenue}
              onChange={(e) => setExactVenue(e.target.value)}
              placeholder="Leave blank while TBA"
              className="mt-1.5"
            />
          </div>
        </div>

        <div>
          <label htmlFor="ev-contacts" className="block text-sm font-semibold text-champagne">
            Reservation phone numbers (comma-separated)
          </label>
          <Input
            id="ev-contacts"
            value={contactsStr}
            onChange={(e) => setContactsStr(e.target.value)}
            className="mt-1.5"
          />
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <label htmlFor="ev-glimit" className="block text-sm font-semibold text-champagne">
              Global invitation limit (blank = unlimited)
            </label>
            <Input
              id="ev-glimit"
              type="number"
              min={1}
              value={globalLimitStr}
              onChange={(e) => setGlobalLimitStr(e.target.value)}
              className="mt-1.5"
            />
          </div>
          <div>
            <label htmlFor="ev-mbulk" className="block text-sm font-semibold text-champagne">
              Max links per bulk request
            </label>
            <Input
              id="ev-mbulk"
              type="number"
              min={1}
              max={500}
              required
              value={maxBulk}
              onChange={(e) => setMaxBulk(Number(e.target.value))}
              className="mt-1.5"
            />
          </div>
        </div>

        <div className="space-y-3 rounded-md border border-champagne/20 bg-midnight p-4 text-sm">
          <label className="flex cursor-pointer items-center justify-between gap-4">
            <span>Display exact venue publicly on homepage</span>
            <input
              type="checkbox"
              checked={venuePublic}
              onChange={(e) => setVenuePublic(e.target.checked)}
              className="h-5 w-5 accent-burnt"
            />
          </label>
          <label className="flex cursor-pointer items-center justify-between gap-4">
            <span>Invitation claiming enabled</span>
            <input
              type="checkbox"
              checked={claimingEnabled}
              onChange={(e) => setClaimingEnabled(e.target.checked)}
              className="h-5 w-5 accent-burnt"
            />
          </label>
          <label className="flex cursor-pointer items-center justify-between gap-4">
            <span>Entrance QR &amp; manual admission enabled</span>
            <input
              type="checkbox"
              checked={admissionEnabled}
              onChange={(e) => setAdmissionEnabled(e.target.checked)}
              className="h-5 w-5 accent-burnt"
            />
          </label>
          <label className="flex cursor-pointer items-center justify-between gap-4">
            <span>Public social sharing webpages &amp; artwork enabled</span>
            <input
              type="checkbox"
              checked={publicSharingEnabled}
              onChange={(e) => setPublicSharingEnabled(e.target.checked)}
              className="h-5 w-5 accent-burnt"
            />
          </label>
        </div>

        <Button type="submit" size="lg" loading={saving}>
          <Save className="h-4 w-4" />
          Save Event Settings
        </Button>
      </form>
    </div>
  );
}

function SettingsLoader() {
  const { data: settings, isLoading } = useQuery({
    queryKey: ["admin-event-settings"],
    queryFn: () => apiFetch<AdminEventSettings>("/api/event/settings/"),
  });

  if (isLoading || !settings) {
    return <p className="text-sm text-ivory-muted">Loading event settings...</p>;
  }

  return <SettingsForm key={settings.updated_at} settings={settings} />;
}

export default function AdminSettingsPage() {
  return (
    <AdminGuardShell requireSuperAdmin>
      <SettingsLoader />
    </AdminGuardShell>
  );
}
