export type AdminRole = "SUPER_ADMIN" | "ADMIN";

export type InvitationStatus = "UNUSED" | "CLAIMED" | "EXPIRED" | "REVOKED";

export type MasterLinkStatus = "ACTIVE" | "PAUSED" | "EXHAUSTED" | "CLOSED" | "EXPIRED";

export type GuestGender = "MALE" | "FEMALE";

export type EmailDeliveryStatus =
  | "NOT_SCHEDULED"
  | "PENDING"
  | "PROCESSING"
  | "SENT"
  | "DELIVERED"
  | "FAILED"
  | "BOUNCED"
  | "CANCELLED";

export interface PublicEvent {
  name: string;
  subtitle: string;
  tagline: string;
  organizers: string;
  hashtag: string;
  event_date: string;
  start_time: string | null;
  end_time: string | null;
  location: string;
  venue_display: string | null;
  venue_is_public: boolean;
  reservation_contacts: string[];
  reservation_contact_links?: Array<{ display: string; whatsapp_url: string }>;
  time_zone: string;
  age_restriction: string;
  claiming_enabled: boolean;
  public_sharing_enabled: boolean;
}

export interface AdminEventSettings {
  id: string;
  name: string;
  subtitle: string;
  tagline: string;
  organizers: string;
  hashtag: string;
  event_date: string;
  start_time: string | null;
  end_time: string | null;
  location: string;
  exact_venue: string;
  venue_is_public: boolean;
  reservation_contacts: string[];
  reservation_contact_links?: Array<{ display: string; whatsapp_url: string }>;
  time_zone: string;
  age_restriction: string;
  global_invitation_limit: number | null;
  max_bulk_quantity: number;
  claim_deadline: string | null;
  claiming_enabled: boolean;
  admission_enabled: boolean;
  public_sharing_enabled: boolean;
  updated_at: string;
}

export interface AdminUser {
  id: string;
  email: string;
  display_name: string;
  role: AdminRole;
  invitation_limit: number | null;
  invitations_generated_count: number;
  is_active: boolean;
  last_login: string | null;
  created_at: string;
}

export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface InvitationSummary {
  id: string;
  reference: string;
  nickname: string;
  guest_email: string;
  gender: GuestGender | "";
  status: InvitationStatus;
  latest_email_status: EmailDeliveryStatus;
  is_admitted: boolean;
  checked_in_at: string | null;
  generated_by: string;
  generated_by_name: string;
  generated_by_email: string;
  master_link_id: string | null;
  master_link_name: string | null;
  generated_at: string;
  expires_at: string | null;
  claimed_at: string | null;
  revoked_at: string | null;
  revocation_reason: string;
  show_nickname_publicly: boolean;
  public_sharing_enabled: boolean;
  can_manage: boolean;
}

export interface InvitationDetail extends InvitationSummary {
  claim_url: string | null;
  revoked_by_name: string | null;
  admission_credential_version: number;
  checkin_details: {
    id: string;
    checked_in_at: string;
    verification_method: "QR" | "MANUAL";
    verified_by_name: string;
    notes: string;
  } | null;
}

export interface BulkGenerateResponse {
  count: number;
  items: Array<{
    id: string;
    reference: string;
    claim_url: string;
    expires_at: string | null;
    generated_at: string;
  }>;
  remaining_global_quota: number | null;
  remaining_admin_quota: number | null;
}

export interface MasterLinkSummary {
  id: string;
  name: string;
  max_tickets: number;
  claimed_count: number;
  remaining_tickets: number;
  released_tickets: number;
  status: MasterLinkStatus;
  created_by: string;
  created_by_name: string;
  created_by_email: string;
  created_at: string;
  expires_at: string | null;
  paused_at: string | null;
  closed_at: string | null;
  closed_by_name: string | null;
  claim_url: string | null;
  can_manage: boolean;
}

export interface MasterLinkCreateResponse extends MasterLinkSummary {
  remaining_global_quota: number | null;
  remaining_admin_quota: number | null;
}

export interface EmailDeliveryRecord {
  id: string;
  email_type: string;
  recipient_email: string;
  admission_credential_version: number | null;
  status: EmailDeliveryStatus;
  provider: string;
  provider_message_id: string;
  attempt_count: number;
  max_attempts: number;
  next_retry_at: string;
  last_attempted_at: string | null;
  sent_at: string | null;
  delivered_at: string | null;
  failure_reason: string;
  created_at: string;
}

export type GuestInviteState =
  | "VALID_UNUSED"
  | "INVITATION_ALREADY_CLAIMED"
  | "INVITATION_EXPIRED"
  | "INVITATION_REVOKED"
  | "INVALID_INVITATION"
  | "CLAIMING_DISABLED"
  | "MASTER_LINK_EXHAUSTED"
  | "MASTER_LINK_PAUSED"
  | "MASTER_LINK_CLOSED";

export interface GuestInviteInspection {
  state: GuestInviteState;
  claimable: boolean;
  expires_at?: string | null;
  event: PublicEvent;
}

export type ArtworkFormat = "story" | "square" | "portrait" | "preview";

export interface ClaimReceiptPayload {
  nickname: string;
  guest_email: string;
  reference: string;
  claimed_at: string;
  email_delivery_status: EmailDeliveryStatus;
  show_nickname_publicly: boolean;
  public_sharing_enabled: boolean;
  event_sharing_enabled: boolean;
  sharing_version: number;
  share_token: string | null;
  share_url: string | null;
  artwork_urls: Partial<Record<ArtworkFormat, string>>;
  event: PublicEvent;
}

export interface PublicSharePayload {
  event: PublicEvent;
  nickname: string | null;
  show_nickname_publicly: boolean;
  sharing_version: number;
  share_url: string;
  artwork_urls: Record<ArtworkFormat, string>;
}

export interface VerificationResult {
  result_code:
    | "VALID"
    | "ALREADY_ADMITTED"
    | "INVITATION_REVOKED"
    | "INVALID_QR_CODE"
    | "INVALID_INVITATION"
    | "ADMISSION_DISABLED";
  can_admit: boolean;
  message: string;
  verification_method: "QR" | "MANUAL";
  invitation_id?: string;
  reference?: string;
  nickname?: string | null;
  guest_email?: string;
  status?: string;
  claimed_at?: string;
  generated_by_name?: string;
  checked_in_at?: string;
  verified_by_name?: string;
  previous_method?: string;
  revoked_at?: string;
  revocation_reason?: string;
  manual_warning?: string;
}

export interface CheckInRecord {
  id: string;
  invitation: string;
  reference: string;
  nickname: string;
  guest_email: string;
  gender: GuestGender | "";
  verified_by: string;
  verified_by_name: string;
  checked_in_at: string;
  verification_method: "QR" | "MANUAL";
  notes: string;
}

export interface DashboardStats {
  total_generated: number;
  available_unused: number;
  claimed: number;
  expired: number;
  revoked: number;
  emails_pending: number;
  emails_sent: number;
  emails_delivered: number;
  emails_failed: number;
  guests_admitted: number;
  guests_awaiting_admission: number;
  claim_rate_percent: number;
  attendance_rate_percent: number;
  gender_breakdown: {
    claimed: {
      male: number;
      female: number;
      male_percent: number;
      female_percent: number;
    };
    admitted: {
      male: number;
      female: number;
      male_percent: number;
      female_percent: number;
    };
  };
  quota: {
    global_limit: number | null;
    global_used: number;
    global_remaining: number | null;
    admin_limit: number | null;
    admin_used: number;
    admin_remaining: number | null;
    max_bulk_quantity: number;
  };
  event_flags: {
    claiming_enabled: boolean;
    admission_enabled: boolean;
    public_sharing_enabled: boolean;
  };
}

export interface AuditLogRecord {
  id: string;
  actor: string | null;
  actor_email: string;
  actor_display_name: string;
  action_type: string;
  target_type: string;
  target_id: string;
  metadata: Record<string, unknown>;
  ip_address: string | null;
  created_at: string;
}
