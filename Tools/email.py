import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

def send_email(to_email: str, subject: str, body: str) -> str:
    """
    Sends an email using Gmail SMTP.
    Requires GMAIL_ID and PASSWORD (App Password) in .env file.
    """
    gmail_user = os.getenv("GMAIL_ID")
    gmail_password = os.getenv("PASSWORD")

    if not gmail_user or not gmail_password:
        return "ERROR: GMAIL_ID or PASSWORD not found in environment variables."

    try:
        # Create message
        msg = MIMEMultipart()
        msg['From'] = gmail_user
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        # Connect to Gmail SMTP server
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(gmail_user, gmail_password)
        text = msg.as_string()
        server.sendmail(gmail_user, to_email, text)
        server.quit()

        return f"Email sent successfully to {to_email}"
    except Exception as e:
        return f"ERROR failed to send email: {str(e)}"

if __name__ == "__main__":
    # Test block
    print(send_email("test@example.com", "Test Subject", "Hello from OpenClaw Rabbit!"))
