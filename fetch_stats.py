"""
fetch_stats.py
Fetches daily earnings stats from the Dreamliner API and appends a record to
data/history.json.  Designed to run once per day via GitHub Actions.
"""

import auth_helper
import json
import os
import sys
from datetime import datetime, timezone

import requests

# ── Configuration ────────────────────────────────────────────────────────────
STATS_API_URL = "https://api.dreamliner.scaler.com/v1/earnings/stats"
TOKEN_FILE = "tokens.json"
HISTORY_FILE = "data/history.json"

INITIAL_AUTH_TOKEN = os.environ.get("SCALER_AUTH", "")


# ── Token helpers ─────────────────────────────────────────────────────────────
def load_valid_token():
    if os.path.exists(TOKEN_FILE):
        try:
            with open(TOKEN_FILE) as f:
                data = json.load(f)
                token = data.get("access_token")
                if token:
                    return token
        except Exception:
            pass
    return INITIAL_AUTH_TOKEN


def save_access_token(token):
    try:
        with open(TOKEN_FILE, "w") as f:
            json.dump({"access_token": token}, f)
    except Exception as e:
        print(f"Error saving token: {e}")


def refresh_token():
    print("🔄 Token expired – starting Gmail Auto-Login…")
    try:
        new_token = auth_helper.full_login_flow()
        if new_token:
            print("✅ Got new token via Gmail.")
            save_access_token(new_token)
            return new_token
        print("❌ Gmail login failed.")
    except Exception as e:
        print(f"Auto-Login error: {e}")
    return None


# ── API call ──────────────────────────────────────────────────────────────────
def fetch_stats():
    token = load_valid_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Origin": "https://dreamliner.scaler.com",
        "Referer": "https://dreamliner.scaler.com/",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/145.0.0.0 Safari/537.36"
        ),
    }

    print("📊 Fetching stats from Dreamliner API…")
    response = requests.get(STATS_API_URL, headers=headers)

    if response.status_code == 401:
        print("⚠️  Token expired (401) – refreshing…")
        new_token = refresh_token()
        if not new_token:
            return None
        headers["Authorization"] = f"Bearer {new_token}"
        response = requests.get(STATS_API_URL, headers=headers)

    if response.status_code == 200:
        return response.json()

    print(f"❌ API error: {response.status_code} – {response.text}")
    return None


# ── History helpers ───────────────────────────────────────────────────────────
def load_history():
    os.makedirs("data", exist_ok=True)
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return []


def save_history(history):
    os.makedirs("data", exist_ok=True)
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    stats = fetch_stats()
    if not stats:
        print("Could not fetch stats. Exiting.")
        sys.exit(1)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    print(f"📅 Recording stats for {today}")

    history = load_history()

    # Cumulative totals from the API
    approved_count = stats.get("approved_tasks", {}).get("count", 0)
    approved_earnings = stats.get("approved_tasks", {}).get("earnings", 0)
    total_earnings = stats.get("total_earnings", 0)
    pending_count = stats.get("pending_approval", {}).get("count", 0)
    pending_earnings = stats.get("pending_earnings", 0)

    # Calculate daily delta vs previous record
    if history:
        prev = history[-1]
        daily_tasks = approved_count - prev.get("cumulative_approved_count", 0)
        daily_earnings = approved_earnings - prev.get("cumulative_approved_earnings", 0)
    else:
        daily_tasks = approved_count
        daily_earnings = approved_earnings

    # If the last record is already for today, overwrite it instead of appending
    if history and history[-1].get("date") == today:
        history[-1].update(
            {
                "cumulative_approved_count": approved_count,
                "cumulative_approved_earnings": approved_earnings,
                "cumulative_total_earnings": total_earnings,
                "pending_count": pending_count,
                "pending_earnings": pending_earnings,
                "daily_tasks": daily_tasks,
                "daily_earnings": daily_earnings,
                "earnings_breakdown": stats.get("earnings_breakdown", ""),
            }
        )
        print(f"✏️  Updated existing record for {today}")
    else:
        record = {
            "date": today,
            "cumulative_approved_count": approved_count,
            "cumulative_approved_earnings": approved_earnings,
            "cumulative_total_earnings": total_earnings,
            "pending_count": pending_count,
            "pending_earnings": pending_earnings,
            "daily_tasks": daily_tasks,
            "daily_earnings": daily_earnings,
            "earnings_breakdown": stats.get("earnings_breakdown", ""),
        }
        history.append(record)
        print(f"➕ Appended new record for {today}")

    save_history(history)
    print(
        f"✅ Done. Approved: {approved_count} tasks | "
        f"Total Earnings: ₹{total_earnings} | "
        f"Today: {daily_tasks} tasks / ₹{daily_earnings}"
    )


if __name__ == "__main__":
    main()
