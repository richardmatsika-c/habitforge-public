from fastapi_mail import (
    FastMail,
    MessageSchema,
    ConnectionConfig,
    MessageType,
    NameEmail,
)
from pydantic import EmailStr, SecretStr
from typing import List
import os

# --- Configuration ---
conf = ConnectionConfig(
    MAIL_USERNAME=os.getenv("MAIL_USERNAME", "test@example.com"),
    MAIL_PASSWORD=SecretStr(os.getenv("MAIL_PASSWORD", "password")),
    MAIL_FROM=os.getenv("MAIL_FROM", "habits@example.com"),
    MAIL_PORT=int(os.getenv("MAIL_PORT", 587)),
    MAIL_SERVER=os.getenv("MAIL_SERVER", "localhost"),
    MAIL_STARTTLS=False,
    MAIL_SSL_TLS=False,
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=False,
    MAIL_DEBUG=True,
    SUPPRESS_SEND=True,
)

# --- Email Sending Function ---


async def send_reminder_email(recipient: EmailStr, username: str, habit_name: str):
    """
    Sends a single habit reminder email.
    """

    subject = f"Don't forget your habit: {habit_name}!"
    body = f"""
    <p>Hi {username},</p>

    <p>Just a quick reminder to complete your daily habit:</p>

    <h3><strong>{habit_name}</strong></h3>

    <p>You can do it!</p>

    <p>- The HabitForge Team</p>
    """

    # Use a name/email dict so it matches fastapi-mail's NameEmail type
    recipient_entry = NameEmail(name=username, email=str(recipient))

    message = MessageSchema(
        subject=subject,
        recipients=[recipient_entry],
        body=body,
        subtype=MessageType.html,
    )

    fm = FastMail(conf)
    try:
        await fm.send_message(message)
        print(f"Email sent to {recipient} (printed to console).")
    except Exception as e:
        print(f"Failed to send email: {e}")
