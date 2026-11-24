from __future__ import annotations

from django.utils.html import escape

from apps.events.contacts import build_whatsapp_contact_links


def build_invitation_email_content(*, invitation, share_url: str | None) -> tuple[str, str, str]:
    event = invitation.event
    subject = f"You're on the list! Your {event.name} invitation is secured."

    nick_safe = escape(invitation.nickname)
    event_name_safe = escape(event.name)
    organizers_safe = escape(event.organizers)
    date_str = f"{event.event_date.day} {event.event_date.strftime('%B %Y')}"
    location_safe = escape(event.location)
    venue_text = (
        escape(event.exact_venue.strip())
        if (event.venue_is_public and event.exact_venue.strip())
        else "To be announced"
    )
    if event.start_time:
        time_text = event.start_time.strftime("%I:%M %p").lstrip("0")
        if event.end_time:
            time_text += f" – {event.end_time.strftime('%I:%M %p').lstrip('0')}"
    else:
        time_text = "To be announced"

    contact_links = build_whatsapp_contact_links(event)
    contacts_html = " &nbsp;·&nbsp; ".join(
        f'<a href="{escape(c["whatsapp_url"])}" style="color:#FFBE55;text-decoration:underline;font-weight:600;">{escape(c["display"])}</a>'
        for c in contact_links
    )
    contacts_txt = "\n".join(f"  - {c['display']}: {c['whatsapp_url']}" for c in contact_links)

    share_block_html = ""
    share_block_txt = ""
    if share_url:
        safe_url = escape(share_url)
        share_block_html = f"""
        <div style="margin:24px 0;padding:18px;border:1px solid #E85D19;border-radius:8px;background:#26120B;">
          <p style="margin:0 0 10px;color:#F5CE86;font-size:13px;letter-spacing:0.08em;text-transform:uppercase;font-weight:700;">
            Share the Excitement
          </p>
          <p style="margin:0 0 14px;color:#FFF3E0;font-size:14px;line-height:1.6;">
            Let your circle know you're officially on the list using your public promotional link (never share your attached QR admission pass):
          </p>
          <a href="{safe_url}" style="display:inline-block;padding:10px 18px;background:#E85D19;color:#FFF3E0;text-decoration:none;font-weight:700;font-size:13px;border-radius:4px;">
            VIEW PROMOTIONAL SHARE PAGE
          </a>
        </div>
        """
        share_block_txt = f"\nPromotional Share Link (safe to share publicly): {share_url}\n"

    html_body = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>{escape(subject)}</title></head>
<body style="margin:0;padding:24px;background-color:#190D08;color:#FFF3E0;font-family:'Montserrat',Arial,sans-serif;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:580px;margin:0 auto;background-color:#23110A;border:1px solid #F5CE86;border-radius:10px;overflow:hidden;">
    <tr>
      <td style="padding:32px 28px 20px;background-color:#421509;border-bottom:2px solid #E85D19;">
        <p style="margin:0 0 8px;color:#F5CE86;font-size:11px;letter-spacing:0.16em;text-transform:uppercase;font-weight:700;">
          {organizers_safe}
        </p>
        <h1 style="margin:0;color:#FFF3E0;font-size:32px;letter-spacing:0.04em;text-transform:uppercase;">
          {event_name_safe}
        </h1>
        <p style="margin:6px 0 0;color:#FFBE55;font-size:15px;font-style:italic;">
          {escape(event.subtitle)} — {escape(event.tagline)}
        </p>
      </td>
    </tr>
    <tr>
      <td style="padding:28px;">
        <p style="margin:0 0 16px;font-size:16px;color:#FFF3E0;">Hey <strong>{nick_safe}</strong>,</p>
        <p style="margin:0 0 16px;font-size:15px;line-height:1.65;color:#FFF3E0;">
          It's official — you're on the list! Your exclusive invitation to <strong>{event_name_safe}</strong> has been secured.
        </p>
        <p style="margin:0 0 20px;font-size:15px;line-height:1.65;color:#FFF3E0;">
          Your official PDF admission pass is attached to this email (<strong>DRIP-AND-RHYTHM-{escape(invitation.reference)}.pdf</strong>). Open and save the PDF on your phone to present its QR code at the entrance.
        </p>
        <table role="presentation" width="100%" cellspacing="0" cellpadding="8" style="background:#190D08;border:1px solid #421509;border-radius:8px;margin-bottom:20px;font-size:14px;">
          <tr><td style="color:#FFBE55;width:38%;font-weight:700;">Invitation Ref</td><td style="color:#FFF3E0;">{escape(invitation.reference)}</td></tr>
          <tr><td style="color:#FFBE55;font-weight:700;">Date</td><td style="color:#FFF3E0;">{escape(date_str)}</td></tr>
          <tr><td style="color:#FFBE55;font-weight:700;">Time</td><td style="color:#FFF3E0;">{escape(time_text)}</td></tr>
          <tr><td style="color:#FFBE55;font-weight:700;">Location</td><td style="color:#FFF3E0;">{location_safe} ({venue_text})</td></tr>
          <tr><td style="color:#FFBE55;font-weight:700;">Admission</td><td style="color:#FFF3E0;">One person only · Strictly {escape(event.age_restriction)}</td></tr>
        </table>
        <div style="padding:14px 16px;background:#3A120D;border-left:4px solid #A51B12;border-radius:4px;margin-bottom:20px;">
          <p style="margin:0;color:#FFF3E0;font-size:13px;line-height:1.5;">
            <strong>Security Notice:</strong> Do not post or forward your attached PDF admission QR code. Each QR code admits one guest only.
          </p>
        </div>
        {share_block_html}
        <p style="margin:20px 0 6px;font-size:15px;color:#F5CE86;font-weight:600;">
          The drip is ready. The rhythm is calling. See you there.
        </p>
        <p style="margin:0;font-size:13px;color:#FFBE55;">{organizers_safe}</p>
        <hr style="border:none;border-top:1px solid #421509;margin:24px 0 14px;">
        <p style="margin:0;font-size:12px;color:#F5CE86;line-height:1.6;">
          Reservations &amp; Inquiries (WhatsApp):<br>
          {contacts_html}
        </p>
      </td>
    </tr>
  </table>
</body>
</html>"""

    text_body = (
        f"Hey {invitation.nickname},\n\n"
        f"It's official — you're on the list!\n"
        f"Your exclusive invitation to {event.name} has been secured.\n\n"
        f"Date: {date_str}\n"
        f"Time: {time_text}\n"
        f"Location: {event.location} ({venue_text})\n"
        f"Invitation Reference: {invitation.reference}\n"
        f"Admission: One person only · Strictly {event.age_restriction}\n\n"
        f"Your official PDF admission pass is attached to this email. Please present its QR code at the entrance.\n"
        f"IMPORTANT: Never share your official PDF or QR code publicly.\n"
        f"{share_block_txt}\n"
        f"The drip is ready. The rhythm is calling.\n"
        f"See you there.\n\n"
        f"{event.organizers}\n"
        f"Reservations & Inquiries (WhatsApp):\n{contacts_txt}\n"
    )
    return subject, html_body, text_body


def build_password_reset_email_content(*, display_name: str, reset_url: str) -> tuple[str, str, str]:
    subject = "DRIP & RHYTHM — Administrator Password Reset"
    safe_name = escape(display_name)
    safe_url = escape(reset_url)
    html_body = f"""<!DOCTYPE html>
<html lang="en">
<body style="margin:0;padding:24px;background:#190D08;color:#FFF3E0;font-family:Arial,sans-serif;">
  <div style="max-width:520px;margin:0 auto;padding:28px;background:#23110A;border:1px solid #F5CE86;border-radius:8px;">
    <h2 style="margin:0 0 14px;color:#F5CE86;">DRIP &amp; RHYTHM Admin Security</h2>
    <p>Hello {safe_name},</p>
    <p>A password reset was requested for your administrator account. Use the secure link below within 60 minutes:</p>
    <p style="margin:22px 0;">
      <a href="{safe_url}" style="padding:12px 20px;background:#E85D19;color:#FFF3E0;text-decoration:none;font-weight:700;border-radius:4px;">
        Reset Administrator Password
      </a>
    </p>
    <p style="font-size:12px;color:#F5CE86;">If you did not request this reset, you can safely ignore this message.</p>
  </div>
</body>
</html>"""
    text_body = (
        f"Hello {display_name},\n\n"
        f"A password reset was requested for your DRIP & RHYTHM administrator account.\n"
        f"Open this link within 60 minutes to set a new password:\n\n{reset_url}\n\n"
        f"If you did not request this reset, ignore this email.\n"
    )
    return subject, html_body, text_body
