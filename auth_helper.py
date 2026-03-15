import imaplib
import email
import re
import requests
import time
import os

# --- CONFIGURATION ---
GMAIL_USER = os.environ.get("GMAIL_USER", "")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_PASSWORD", "")
SCALER_LOGIN_URL = "https://api.dreamliner.scaler.com/v1/auth/login/magic-link"
# Seconds to wait after requesting the magic-link email so it has time to arrive
EMAIL_ARRIVAL_WAIT_SECONDS = 15


def trigger_login_email():
    """Tells Scaler to send a fresh login email."""
    print("📧 Requesting new login email from Scaler...")
    payload = {
        "email": GMAIL_USER,
        "callback_url": "https://dreamliner.scaler.com/auth/verify",
    }
    try:
        requests.post(SCALER_LOGIN_URL, json=payload)
        print("✅ Email requested. Waiting for it to arrive...")
        time.sleep(EMAIL_ARRIVAL_WAIT_SECONDS)
    except Exception as e:
        print(f"❌ Failed to trigger email: {e}")


def get_latest_magic_link():
    """Logs into Gmail and grabs the link from the latest Scaler email."""
    print("Opening Inbox...")
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        mail.select("inbox")

        status, messages = mail.search(None, '(FROM "noreply@dreamliner.scaler.com")')
        if not messages[0]:
            print("❌ No emails found from Scaler.")
            return None, None

        latest_email_id = messages[0].split()[-1]
        status, data = mail.fetch(latest_email_id, "(RFC822)")
        raw_email = data[0][1]
        msg = email.message_from_bytes(raw_email)

        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/html":
                    body = part.get_payload(decode=True).decode()
                    break
        else:
            body = msg.get_payload(decode=True).decode()

        link_pattern = re.search(
            r"https://dreamliner\.scaler\.com/auth/verify\?token=([a-zA-Z0-9_\-\.]+)",
            body,
        )

        if link_pattern:
            full_link = link_pattern.group(0)
            verify_token = link_pattern.group(1)
            print("🔗 Found Magic Link!")
            return full_link, verify_token
        else:
            print("❌ Could not find link in email body.")
            return None, None

    except Exception as e:
        print(f"❌ Gmail Error: {e}")
        return None, None


def exchange_link_for_token(verify_token):
    """Exchanges the email verification token for the real Access Token."""
    verify_api_url = (
        "https://api.dreamliner.scaler.com/v1/auth/magic-link/verify"
    )
    try:
        response = requests.post(verify_api_url, json={"token": verify_token})
        if response.status_code == 200:
            data = response.json()
            return data.get("token") or data.get("access_token")
    except Exception:
        pass
    return verify_token


def full_login_flow():
    trigger_login_email()
    link, verify_token = get_latest_magic_link()

    if verify_token:
        final_token = exchange_link_for_token(verify_token)
        return final_token
    return None
