import smtplib
from email.message import EmailMessage

from app.core.config import settings


def send_email_otp(to_email: str, otp: str):
    message = EmailMessage()
    message["Subject"] = "Nutrio Meals Email Verification OTP | رمز التحقق"
    message["From"] = settings.MAIL_FROM
    message["To"] = to_email

    message.set_content(
        f"""
Hello,

Your Nutrio Meals verification code is:

{otp}

This code will expire in 10 minutes.

Thank you,
Nutrio Meals Team


----------------------------------------


مرحباً،

رمز التحقق الخاص بك في Nutrio Meals هو:

{otp}

ستنتهي صلاحية هذا الرمز خلال 10 دقائق.

شكراً لك،
فريق Nutrio Meals
"""
    )

    with smtplib.SMTP(settings.MAIL_SERVER, settings.MAIL_PORT) as smtp:
        smtp.starttls()
        smtp.login(settings.MAIL_USERNAME, settings.MAIL_PASSWORD)
        smtp.send_message(message)