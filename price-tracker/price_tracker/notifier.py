"""Alert delivery: Telegram (primary) and email (secondary), both optional.

Neither channel is required for the project to run -- if nothing is
configured, alerts are simply logged, which keeps local development and
tests friction-free.
"""
from __future__ import annotations

import logging
import smtplib
from email.mime.text import MIMEText

import requests

from .config import settings

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


def send_telegram(message: str) -> bool:
    if not settings.telegram_configured:
        return False
    url = TELEGRAM_API.format(token=settings.telegram_bot_token)
    try:
        resp = requests.post(
            url,
            json={"chat_id": settings.telegram_chat_id, "text": message, "parse_mode": "Markdown"},
            timeout=10,
        )
        resp.raise_for_status()
        return True
    except requests.RequestException as exc:  # pragma: no cover - network dependent
        logger.error("Telegram notification failed: %s", exc)
        return False


def send_email(subject: str, message: str) -> bool:
    if not settings.email_configured:
        return False
    msg = MIMEText(message)
    msg["Subject"] = subject
    msg["From"] = settings.smtp_user
    msg["To"] = settings.alert_email_to
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_password)
            server.sendmail(settings.smtp_user, [settings.alert_email_to], msg.as_string())
        return True
    except (smtplib.SMTPException, OSError) as exc:  # pragma: no cover - network dependent
        logger.error("Email notification failed: %s", exc)
        return False


def notify_price_drop(product_name: str, url: str, old_price: float, new_price: float,
                       currency: str, is_all_time_low: bool) -> None:
    headline = "ALL-TIME LOW" if is_all_time_low else "Price drop"
    message = (
        f"*{headline}*: {product_name}\n"
        f"{currency} {old_price:,.2f} -> {currency} {new_price:,.2f}\n"
        f"{url}"
    )
    sent_telegram = send_telegram(message)
    sent_email = send_email(f"[Price Tracker] {headline}: {product_name}", message)

    if not sent_telegram and not sent_email:
        logger.info("ALERT (no channel configured, logging only): %s", message.replace("\n", " | "))
