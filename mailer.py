import smtplib
from email.mime.text import MIMEText
import os
from backend.config import get_settings

settings = get_settings()

def send_email(to_email: str, subject: str, content: str):
    print("DEBUG: send_email called with", to_email, subject)
    try:
        print("DEBUG: Creating MIMEText")
        msg = MIMEText(content)
        msg["Subject"] = subject
        msg["From"] = settings.email_from
        msg["To"] = to_email

        print("DEBUG: Checking SMTP port:", settings.smtp_port)
        if settings.smtp_port == 465:
            print("DEBUG: Using SMTP_SSL")
            with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port) as smtp:
                smtp.login(settings.smtp_username, settings.smtp_password)
                smtp.send_message(msg)
        elif settings.smtp_port == 587:
            print("DEBUG: Using SMTP with STARTTLS")
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as smtp:
                smtp.ehlo()
                smtp.starttls()
                smtp.ehlo()
                smtp.login(settings.smtp_username, settings.smtp_password)
                smtp.send_message(msg)
        else:
            print("DEBUG: Unsupported SMTP port")
            raise ValueError(f"Unsupported SMTP port: {settings.smtp_port}")
        print("DEBUG: Email sent successfully")
        return True
    except Exception as e:
        print("ERROR SENDING EMAIL:", e)
        import traceback
        traceback.print_exc()
        return False
