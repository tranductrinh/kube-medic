"""
Email Tools.

This module provides tools for sending email notifications:
- send_email: Send a structured investigation report via email
"""

import smtplib
from email.mime.text import MIMEText

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from kube_medic.config import get_settings
from kube_medic.logging_config import get_logger

logger = get_logger(__name__)


# =============================================================================
# EMAIL TEMPLATES
# =============================================================================

EMAIL_SUBJECT_TEMPLATE = "[KubeMedic] {summary}"

EMAIL_BODY_HTML = """<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f5f5f5;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color: #f5f5f5;">
    <tr>
      <td align="center" style="padding: 40px 20px;">
        <table role="presentation" width="600" cellspacing="0" cellpadding="0" style="background-color: #ffffff; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">

          <!-- Header -->
          <tr>
            <td style="background: linear-gradient(135deg, #1a73e8 0%, #0d47a1 100%); padding: 30px 40px; border-radius: 8px 8px 0 0;">
              <h1 style="margin: 0; color: #ffffff; font-size: 24px; font-weight: 600;">
                &#9881; KubeMedic
              </h1>
              <p style="margin: 8px 0 0 0; color: rgba(255,255,255,0.9); font-size: 14px;">
                Investigation Report
              </p>
            </td>
          </tr>

          <!-- Summary -->
          <tr>
            <td style="padding: 30px 40px 20px 40px;">
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
                <tr>
                  <td style="background-color: #e3f2fd; border-left: 4px solid #1a73e8; padding: 16px 20px; border-radius: 0 4px 4px 0;">
                    <h2 style="margin: 0 0 8px 0; color: #1a73e8; font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;">
                      Summary
                    </h2>
                    <p style="margin: 0; color: #1a1a1a; font-size: 16px; line-height: 1.5;">
                      {summary}
                    </p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Root Cause -->
          <tr>
            <td style="padding: 10px 40px 20px 40px;">
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
                <tr>
                  <td style="background-color: #fce4ec; border-left: 4px solid #c62828; padding: 16px 20px; border-radius: 0 4px 4px 0;">
                    <h2 style="margin: 0 0 8px 0; color: #c62828; font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;">
                      Root Cause
                    </h2>
                    <p style="margin: 0; color: #1a1a1a; font-size: 14px; line-height: 1.6;">
                      {root_cause}
                    </p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Evidence -->
          <tr>
            <td style="padding: 10px 40px 20px 40px;">
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
                <tr>
                  <td style="background-color: #f5f5f5; border-left: 4px solid #616161; padding: 16px 20px; border-radius: 0 4px 4px 0;">
                    <h2 style="margin: 0 0 8px 0; color: #616161; font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;">
                      Evidence
                    </h2>
                    <p style="margin: 0; color: #1a1a1a; font-size: 14px; line-height: 1.6; white-space: pre-wrap;">
                      {evidence}
                    </p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Recommended Fix -->
          <tr>
            <td style="padding: 10px 40px 30px 40px;">
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
                <tr>
                  <td style="background-color: #e8f5e9; border-left: 4px solid #2e7d32; padding: 16px 20px; border-radius: 0 4px 4px 0;">
                    <h2 style="margin: 0 0 8px 0; color: #2e7d32; font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;">
                      Recommended Fix
                    </h2>
                    <div style="margin: 0; color: #1a1a1a; font-size: 14px; line-height: 1.6;">
                      <pre style="margin: 0; font-family: 'SF Mono', Monaco, 'Courier New', monospace; font-size: 13px; background-color: #f8f9fa; padding: 12px; border-radius: 4px; overflow-x: auto; white-space: pre-wrap; word-wrap: break-word;">{recommended_fix}</pre>
                    </div>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="background-color: #fafafa; padding: 20px 40px; border-radius: 0 0 8px 8px; border-top: 1px solid #e0e0e0;">
              <p style="margin: 0; color: #9e9e9e; font-size: 12px; text-align: center;">
                This report was generated automatically by KubeMedic
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


# =============================================================================
# INPUT SCHEMAS
# =============================================================================

class SendEmailInput(BaseModel):
    """Input schema for sending structured investigation email."""

    summary: str = Field(..., description="Concise overview of the issue (used in subject line)")
    root_cause: str = Field(..., description="Concise explanation of the root cause")
    evidence: str = Field(..., description="What was checked and found during investigation")
    recommended_fix: str = Field(..., description="Specific kubectl commands or steps to fix (never auto-execute)")


# =============================================================================
# TOOLS
# =============================================================================

@tool(args_schema=SendEmailInput)
def send_email(
        summary: str,
        root_cause: str,
        evidence: str,
        recommended_fix: str,
) -> str:
    """
    Send a structured investigation report via email.

    The email includes: Summary, Root Cause, Evidence, and Recommended Fix.
    The recipient is configured via EMAIL_TO environment variable.
    """
    settings = get_settings()

    # Validate email configuration
    if not settings.smtp_host:
        return "Error: Email not configured. SMTP_HOST is not set."

    if not settings.email_from:
        return "Error: Email not configured. EMAIL_FROM is not set."

    if not settings.email_to:
        return "Error: Email not configured. EMAIL_TO is not set."

    to = settings.email_to

    # Format subject and body using templates
    subject = EMAIL_SUBJECT_TEMPLATE.format(summary=summary)
    html_body = EMAIL_BODY_HTML.format(
        summary=summary,
        root_cause=root_cause,
        evidence=evidence,
        recommended_fix=recommended_fix,
    )

    logger.info(f"Sending investigation report to {to}: {subject}")

    try:
        # Create HTML email message
        msg = MIMEText(html_body, "html")
        msg["Subject"] = subject
        msg["From"] = settings.email_from
        msg["To"] = to

        # Connect and send
        if settings.smtp_use_tls:
            server = smtplib.SMTP(settings.smtp_host, settings.smtp_port)
            server.starttls()
        else:
            server = smtplib.SMTP(settings.smtp_host, settings.smtp_port)

        # Authenticate if credentials provided
        if settings.smtp_username and settings.smtp_password:
            server.login(settings.smtp_username, settings.smtp_password)

        server.sendmail(settings.email_from, to, msg.as_string())
        server.quit()

        logger.info(f"Investigation report sent successfully to {to}")
        return f"Investigation report sent successfully to {to}"

    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"SMTP authentication failed: {e}")
        return "Error: SMTP authentication failed. Check credentials."
    except smtplib.SMTPConnectError as e:
        logger.error(f"SMTP connection failed: {e}")
        return f"Error: Could not connect to SMTP server {settings.smtp_host}:{settings.smtp_port}"
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        return f"Error: Failed to send email: {e}"


# =============================================================================
# TOOL COLLECTION (for easy import)
# =============================================================================

email_tools = [
    send_email,
]
