from __future__ import annotations

import html
import smtplib
from email.message import EmailMessage

from app.core.config import settings


def _send_email_message(message: EmailMessage) -> None:
    """
    Send an email using the SMTP settings already used by NutrioMeals.

    Supports either implicit SSL or STARTTLS. Exceptions are intentionally
    allowed to propagate so callers can log them. Business transactions should
    commit before this function is called.
    """
    if settings.EMAIL_SSL:
        with smtplib.SMTP_SSL(
            settings.EMAIL_SERVER,
            settings.EMAIL_PORT,
            timeout=20,
        ) as smtp:
            smtp.login(
                settings.EMAIL_USERNAME,
                settings.EMAIL_PASSWORD,
            )
            smtp.send_message(message)
        return

    with smtplib.SMTP(
        settings.EMAIL_SERVER,
        settings.EMAIL_PORT,
        timeout=20,
    ) as smtp:
        smtp.ehlo()

        if settings.EMAIL_TLS:
            smtp.starttls()
            smtp.ehlo()

        smtp.login(
            settings.EMAIL_USERNAME,
            settings.EMAIL_PASSWORD,
        )
        smtp.send_message(message)


def send_email_otp(
    to_email: str,
    otp: str,
    purpose: str = "verification",
) -> None:
    if purpose == "password_reset":
        subject = (
            "Nutrio Meals Password Reset OTP | "
            "رمز إعادة تعيين كلمة المرور"
        )
        english_title = "Your password reset code is:"
        arabic_title = (
            "رمز إعادة تعيين كلمة المرور الخاص بك هو:"
        )
    else:
        subject = (
            "Nutrio Meals Email Verification OTP | "
            "رمز التحقق"
        )
        english_title = (
            "Your Nutrio Meals verification code is:"
        )
        arabic_title = (
            "رمز التحقق الخاص بك في Nutrio Meals هو:"
        )

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

    _send_email_message(message)


def send_driver_ready_email(
    *,
    to_email: str,
    driver_name: str,
    order_number: str,
    delivery_date: object,
    delivery_time: object,
    login_url: str | None = None,
) -> None:
    """
    Email the assigned driver after an order becomes ready for pickup.

    Customer address, health information and allergy information are not
    included in the email. The driver must sign in to view protected details.
    """
    safe_driver_name = (
        str(driver_name or "").strip()
        or "Driver"
    )
    safe_order_number = str(order_number or "").strip()
    safe_delivery_date = str(delivery_date or "").strip()
    safe_delivery_time = str(delivery_time or "").strip()
    safe_login_url = str(
        login_url
        or "https://nutriomeals.com/login"
    ).strip()

    subject = (
        f"NutrioMeals: Order {safe_order_number} "
        "is ready for pickup"
    )

    plain_text = f"""Hello {safe_driver_name},

Order {safe_order_number} is now ready for pickup.

Delivery date: {safe_delivery_date}
Delivery time: {safe_delivery_time}

Please sign in to the NutrioMeals Driver Portal to view the customer,
pickup and delivery details:

{safe_login_url}

For customer privacy, protected delivery and health details are available
only after you sign in.

Thank you,
NutrioMeals Team
"""

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.EMAIL_FROM
    message["To"] = to_email
    message.set_content(plain_text)

    escaped_name = html.escape(safe_driver_name)
    escaped_order = html.escape(safe_order_number)
    escaped_date = html.escape(safe_delivery_date)
    escaped_time = html.escape(safe_delivery_time)
    escaped_url = html.escape(safe_login_url, quote=True)

    message.add_alternative(
        f"""<!doctype html>
<html>
<body style="margin:0;background:#f5f7f2;font-family:Arial,sans-serif;color:#173327;">
  <div style="max-width:620px;margin:0 auto;padding:28px 16px;">
    <div style="background:linear-gradient(135deg,#173327,#6E7A25);padding:24px;border-radius:18px 18px 0 0;color:white;">
      <h1 style="margin:0;font-size:22px;">Delivery Ready for Pickup</h1>
      <p style="margin:8px 0 0;opacity:.8;">NutrioMeals Driver Notification</p>
    </div>
    <div style="background:white;padding:26px;border-radius:0 0 18px 18px;border:1px solid #e5e7eb;">
      <p>Hello <strong>{escaped_name}</strong>,</p>
      <p>Order <strong>{escaped_order}</strong> is now ready for pickup.</p>
      <table style="width:100%;border-collapse:collapse;margin:18px 0;">
        <tr>
          <td style="padding:10px;background:#f7f8f3;border-bottom:1px solid #e5e7eb;"><strong>Delivery date</strong></td>
          <td style="padding:10px;background:#f7f8f3;border-bottom:1px solid #e5e7eb;">{escaped_date}</td>
        </tr>
        <tr>
          <td style="padding:10px;background:#f7f8f3;"><strong>Delivery time</strong></td>
          <td style="padding:10px;background:#f7f8f3;">{escaped_time}</td>
        </tr>
      </table>
      <p style="text-align:center;margin:24px 0;">
        <a href="{escaped_url}" style="display:inline-block;background:#173327;color:white;text-decoration:none;padding:13px 22px;border-radius:10px;font-weight:bold;">
          Open Driver Portal
        </a>
      </p>
      <p style="font-size:13px;color:#6b7280;">
        For customer privacy, protected delivery and health details are shown
        only after you sign in.
      </p>
      <p>Thank you,<br><strong>NutrioMeals Team</strong></p>
    </div>
  </div>
</body>
</html>""",
        subtype="html",
    )

    _send_email_message(message)


def send_driver_ready_group_email(
    *,
    to_email: str,
    driver_name: str,
    orders: list[dict],
    login_url: str | None = None,
) -> None:
    """
    Send one summary email to a driver for several ready pickup orders.

    The email deliberately excludes customer names, phone numbers, addresses,
    allergies, health information and meal details. Protected details remain
    available only inside the authenticated Driver Portal.
    """
    safe_driver_name = (
        str(driver_name or "").strip()
        or "Driver"
    )
    safe_login_url = str(
        login_url
        or "https://nutriomeals.com/login"
    ).strip()

    normalized_orders: list[dict] = []

    for item in orders or []:
        order_number = str(
            item.get("order_number") or ""
        ).strip()

        if not order_number:
            continue

        normalized_orders.append(
            {
                "order_number": order_number,
                "delivery_date": str(
                    item.get("delivery_date") or ""
                ).strip(),
                "delivery_time": str(
                    item.get("delivery_time") or ""
                ).strip(),
            }
        )

    if not normalized_orders:
        raise ValueError(
            "At least one order is required for a grouped driver email"
        )

    count = len(normalized_orders)
    subject = (
        f"NutrioMeals: {count} "
        f"{'delivery' if count == 1 else 'deliveries'} "
        "ready for pickup"
    )

    plain_rows = "\n".join(
        (
            f"- {item['order_number']} | "
            f"{item['delivery_date']} "
            f"{item['delivery_time']}"
        )
        for item in normalized_orders
    )

    plain_text = f"""Hello {safe_driver_name},

{count} {'delivery is' if count == 1 else 'deliveries are'} now ready for pickup.

Orders:
{plain_rows}

Please sign in to the NutrioMeals Driver Portal to view customer,
pickup and delivery details:

{safe_login_url}

For customer privacy, protected customer and delivery details are available
only after you sign in.

Thank you,
NutrioMeals Team
"""

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.EMAIL_FROM
    message["To"] = to_email
    message.set_content(plain_text)

    escaped_name = html.escape(safe_driver_name)
    escaped_url = html.escape(
        safe_login_url,
        quote=True,
    )

    html_rows = "".join(
        (
            "<tr>"
            f"<td style='padding:10px;border-bottom:1px solid #e5e7eb;'>"
            f"<strong>{html.escape(item['order_number'])}</strong>"
            "</td>"
            f"<td style='padding:10px;border-bottom:1px solid #e5e7eb;'>"
            f"{html.escape(item['delivery_date'])}"
            "</td>"
            f"<td style='padding:10px;border-bottom:1px solid #e5e7eb;'>"
            f"{html.escape(item['delivery_time'])}"
            "</td>"
            "</tr>"
        )
        for item in normalized_orders
    )

    message.add_alternative(
        f"""<!doctype html>
<html>
<body style="margin:0;background:#f5f7f2;font-family:Arial,sans-serif;color:#173327;">
  <div style="max-width:680px;margin:0 auto;padding:28px 16px;">
    <div style="background:linear-gradient(135deg,#173327,#6E7A25);padding:24px;border-radius:18px 18px 0 0;color:white;">
      <h1 style="margin:0;font-size:22px;">{count} {'Delivery' if count == 1 else 'Deliveries'} Ready for Pickup</h1>
      <p style="margin:8px 0 0;opacity:.8;">NutrioMeals Driver Summary</p>
    </div>
    <div style="background:white;padding:26px;border-radius:0 0 18px 18px;border:1px solid #e5e7eb;">
      <p>Hello <strong>{escaped_name}</strong>,</p>
      <p>{count} {'delivery is' if count == 1 else 'deliveries are'} now ready for pickup.</p>
      <table style="width:100%;border-collapse:collapse;margin:18px 0;">
        <thead>
          <tr style="background:#f7f8f3;text-align:left;">
            <th style="padding:10px;">Order</th>
            <th style="padding:10px;">Date</th>
            <th style="padding:10px;">Time</th>
          </tr>
        </thead>
        <tbody>{html_rows}</tbody>
      </table>
      <p style="text-align:center;margin:24px 0;">
        <a href="{escaped_url}" style="display:inline-block;background:#173327;color:white;text-decoration:none;padding:13px 22px;border-radius:10px;font-weight:bold;">
          Open Driver Portal
        </a>
      </p>
      <p style="font-size:13px;color:#6b7280;">
        Customer names, phone numbers, addresses, allergies and meal details
        are not included in this email. Sign in to view protected details.
      </p>
      <p>Thank you,<br><strong>NutrioMeals Team</strong></p>
    </div>
  </div>
</body>
</html>""",
        subtype="html",
    )

    _send_email_message(message)
