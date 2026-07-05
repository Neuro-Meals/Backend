import smtplib
from email.message import EmailMessage

from app.core.config import settings


def send_email_otp(to_email: str, otp: str, purpose: str = "verification"):
    if purpose == "password_reset":
        subject = "Nutrio Meals Password Reset OTP | رمز إعادة تعيين كلمة المرور"
        english_title = "Your password reset code is:"
        arabic_title = "رمز إعادة تعيين كلمة المرور الخاص بك هو:"
    else:
        subject = "Nutrio Meals Email Verification OTP | رمز التحقق"
        english_title = "Your Nutrio Meals verification code is:"
        arabic_title = "رمز التحقق الخاص بك في Nutrio Meals هو:"

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.EMAIL_FROM
    message["To"] = to_email

    message.set_content(
        f"""
Hello,

{english_title}

{otp}

This code will expire in 10 minutes.

Thank you,
Nutrio Meals Team


----------------------------------------


مرحباً،

{arabic_title}

{otp}

ستنتهي صلاحية هذا الرمز خلال 10 دقائق.

شكراً لك،
فريق Nutrio Meals
"""
    )

    with smtplib.SMTP(settings.EMAIL_SERVER, settings.EMAIL_PORT) as smtp:
        smtp.starttls()
        smtp.login(settings.EMAIL_USERNAME, settings.EMAIL_PASSWORD)
        smtp.send_message(message)