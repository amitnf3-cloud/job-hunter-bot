#!/usr/bin/env python3
"""ONE-TIME LOCAL SETUP - run this on your own machine, never in CI.

Logs into your Telegram account interactively (phone number, then the login
code Telegram sends you, then your 2FA password if you have one set) and
prints a Telethon StringSession.

That printed string is equivalent to a login credential for your Telegram
account - anyone holding it can read your chats and act as you. Do NOT:
  - save it to a file in this repo
  - commit it, paste it in chat, or share it with anyone
  - print it anywhere other than your own terminal

Instead, store it as the GitHub Actions repository secret
TELEGRAM_SESSION_STRING, alongside TELEGRAM_API_ID and TELEGRAM_API_HASH.

If this string is ever exposed, invalidate it immediately from the Telegram
app: Settings -> Devices -> find the session -> Terminate.

Usage:
    pip install telethon
    python scripts/generate_telegram_session.py
"""

from telethon.sync import TelegramClient
from telethon.sessions import StringSession


def main():
    print("Get api_id and api_hash from https://my.telegram.org (API Development Tools).\n")
    api_id = int(input("api_id: ").strip())
    api_hash = input("api_hash: ").strip()

    with TelegramClient(StringSession(), api_id, api_hash) as client:
        session_string = client.session.save()

    print("\nLogin successful.")
    print("Copy the string below into the TELEGRAM_SESSION_STRING GitHub secret.")
    print("Do not save it to a file or share it with anyone.\n")
    print(session_string)


if __name__ == "__main__":
    main()
