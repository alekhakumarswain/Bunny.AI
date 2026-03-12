import smtplib
import os
import mimetypes
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from dotenv import load_dotenv

load_dotenv()


def send_email(
    to_email: str,
    subject: str,
    body: str,
    is_html: bool = False,
    attachment_paths: list[str] = None,
) -> str:
    """
    Sends an email using Gmail SMTP with optional file attachments.

    Args:
        to_email         : Recipient email address.
        subject          : Email subject line.
        body             : Email body (plain text or HTML).
        is_html          : Set True to send an HTML-formatted email.
        attachment_paths : List of absolute file paths to attach (PDF, DOCX, images, etc.).
                           Pass None or [] for no attachments.
    """
    gmail_user     = os.getenv("GMAIL_ID")
    gmail_password = os.getenv("PASSWORD")

    if not gmail_user or not gmail_password:
        return "ERROR: GMAIL_ID or PASSWORD not found in environment variables."

    # Auto-detect HTML bodies
    if not is_html and body.lstrip().startswith("<"):
        is_html = True

    # Root message: "mixed" supports both alternative text AND attachments
    msg = MIMEMultipart("mixed")
    msg["From"]    = gmail_user
    msg["To"]      = to_email
    msg["Subject"] = subject

    # ── Body part ──────────────────────────────────────────────────
    # Wrap text alternatives in a nested "alternative" container
    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText(
        "This email requires an HTML-capable mail client." if is_html else body,
        "plain"
    ))
    if is_html:
        alt.attach(MIMEText(body, "html"))
    msg.attach(alt)

    # ── Attachments ────────────────────────────────────────────────
    attached_names = []
    if attachment_paths:
        for path in attachment_paths:
            path = path.strip()
            if not os.path.isfile(path):
                print(f"  [Email] ⚠ Attachment not found, skipping: {path}")
                continue

            filename = os.path.basename(path)

            # Detect MIME type
            mime_type, _ = mimetypes.guess_type(path)
            if mime_type:
                main_type, sub_type = mime_type.split("/", 1)
            else:
                main_type, sub_type = "application", "octet-stream"

            with open(path, "rb") as f:
                attach_part = MIMEBase(main_type, sub_type)
                attach_part.set_payload(f.read())

            encoders.encode_base64(attach_part)
            attach_part.add_header(
                "Content-Disposition",
                "attachment",
                filename=filename
            )
            msg.attach(attach_part)
            attached_names.append(filename)
            print(f"  [Email] 📎 Attached: {filename}")

    # ── Send ────────────────────────────────────────────────────────
    try:
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(gmail_user, gmail_password)
        server.sendmail(gmail_user, to_email, msg.as_string())
        server.quit()

        mode   = "HTML" if is_html else "plain text"
        detail = f" | Attachments: {', '.join(attached_names)}" if attached_names else ""
        return f"Email sent successfully to {to_email} ({mode}{detail})"

    except Exception as e:
        return f"ERROR failed to send email: {str(e)}"


if __name__ == "__main__":
    # Quick self-test (no attachment)
    html_body = """
    <html>
      <body style="font-family: Arial, sans-serif; background:#f4f4f4; padding:20px;">
        <h1 style="color:#4CAF50;">Hello from Bunny.AI!</h1>
        <p>This is a <strong>test HTML email</strong>.</p>
      </body>
    </html>
    """
    print(send_email("test@example.com", "HTML Test", html_body, is_html=True))
