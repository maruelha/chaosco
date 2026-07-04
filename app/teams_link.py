"""Teams chat deep links — pure functions, no I/O.

Teams' installed client understands
    https://teams.microsoft.com/l/chat/0/0?users=<emails>&message=<text>
and opens a chat with the message pre-typed; the user reviews and hits Enter.
No API, no credentials, no approvals — it is the user's own Teams client
starting a chat.

What deep links CAN address:
  - 1:1 chat (one email)
  - group chat by MEMBERS (comma-separated emails; optional topicName names
    a newly created group chat)
What they CANNOT address:
  - an existing named group chat / meeting chat by its identity (that needs
    the chat's thread id, which only the Graph API exposes)
  - posting INTO a channel with a pre-filled message (channel links open the
    channel but ignore message text)

The message template can be overridden with `teams_message_template` in
settings.yaml/settings.local.yaml; placeholders: {name} (first word of the
follow-up's with_whom) and {topic}.
"""
from __future__ import annotations

from urllib.parse import quote

DEFAULT_TEMPLATE = "Hi {name}, do you have an update on '{topic}'?"


def build_chat_link(emails: str, message: str, chat_name: str | None = None) -> str:
    """emails: one address or comma-separated list -> 1:1 or group chat.
    chat_name only applies when Teams creates a new group chat."""
    users = ",".join(e.strip() for e in emails.split(",") if e.strip())
    url = ("https://teams.microsoft.com/l/chat/0/0?users="
           + quote(users, safe="@.,"))
    if chat_name and "," in users:
        url += "&topicName=" + quote(chat_name, safe="")
    return url + "&message=" + quote(message, safe="")


def default_message(with_whom: str, topic: str, template: str | None = None) -> str:
    first_name = (with_whom or "").strip().split(" ")[0] or "there"
    return (template or DEFAULT_TEMPLATE).format(name=first_name, topic=topic or "")
