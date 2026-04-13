from __future__ import annotations

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from loguru import logger

from app.config import Settings
from app.dispatcher.markdown_utils import markdown_to_html
from app.models import AttendanceRecord, ExtractedAction, ParticipantNotification


def _wrap_html(body_html: str, title: str = "") -> str:
    """Wrap body HTML in a styled email template."""
    return f"""\
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
</head>
<body style="margin:0;padding:0;background-color:#f4f4f7;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f4f7">
    <tr>
      <td align="center" style="padding:24px 16px">
        <table role="presentation" width="600" cellpadding="0" cellspacing="0"
               style="background-color:#ffffff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.08)">
          <tr>
            <td style="background-color:#2b2d42;padding:20px 32px">
              <h1 style="margin:0;color:#ffffff;font-size:18px;font-weight:600">
                Meeting Summarizer
              </h1>
            </td>
          </tr>
          <tr>
            <td style="padding:28px 32px;color:#333;font-size:14px;line-height:1.6">
              {body_html}
            </td>
          </tr>
          <tr>
            <td style="padding:16px 32px;background-color:#f9f9fb;border-top:1px solid #eee;font-size:12px;color:#888;text-align:center">
              This summary was auto-generated. Please review for accuracy.
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def _smtp_send(
    *,
    to_addr: str,
    subject: str,
    body_plain: str,
    body_html: str | None = None,
    from_addr: str,
    settings: Settings,
) -> bool:
    """Low-level SMTP send shared by action emails and notification emails."""
    if not settings.smtp_username or not settings.smtp_password:
        logger.warning("SMTP credentials not configured — cannot send email")
        return False

    msg = MIMEMultipart("alternative")
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg["Subject"] = subject

    msg.attach(MIMEText(body_plain, "plain"))
    if body_html:
        msg.attach(MIMEText(body_html, "html"))

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(settings.smtp_username, settings.smtp_password)
            server.sendmail(from_addr, [to_addr], msg.as_string())

        logger.success("[Email] Sent '{}' to {}", subject, to_addr)
        return True
    except Exception as exc:
        logger.error("[Email] Failed to send '{}' to {}: {}", subject, to_addr, exc)
        return False


def send_email(
    action: ExtractedAction,
    *,
    participant: AttendanceRecord | None,
    settings: Settings,
) -> bool:
    """Send an email via SMTP for a draft_email action."""
    to_addr = (
        (participant.emailAddress if participant else None)
        or action.payload.intended_recipient
        or settings.email_default_to
    )
    if not to_addr:
        logger.warning("[Email] No recipient resolved for {} — skipping", action.action_id)
        return False

    body = action.payload.draft_body
    html = _wrap_html(markdown_to_html(body), action.payload.subject)

    return _smtp_send(
        to_addr=to_addr,
        subject=action.payload.subject,
        body_plain=body,
        body_html=html,
        from_addr=settings.email_from,
        settings=settings,
    )


def send_notification_email(
    notification: ParticipantNotification,
    *,
    meeting_title: str,
    participant: AttendanceRecord | None,
    settings: Settings,
) -> bool:
    """Email a participant's meeting summary notification."""
    email = participant.emailAddress if participant else None
    name = participant.identity.displayName if participant else notification.id

    if not email:
        logger.warning("[Email] No email for {} — cannot send notification", name)
        return False

    subject = f"Meeting Summary: {meeting_title}"
    body_md = notification.teams_notification_markdown
    html = _wrap_html(markdown_to_html(body_md), subject)

    return _smtp_send(
        to_addr=email,
        subject=subject,
        body_plain=body_md,
        body_html=html,
        from_addr=settings.notification_from_email,
        settings=settings,
    )
