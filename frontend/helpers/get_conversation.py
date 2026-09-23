"""Helper functions"""

from typing import Any

from frontend.services.adk_service import extract_event_text


def get_conversations(session: dict[str, Any]) -> list[dict[str, str]]:
    """Turn an ADK session into a flat list of chat messages.

    The events of a session are not a strict user/model alternation: one user
    question produces several model events (tool calls, tool results, messages
    from sub-agents). Pairing them two by two therefore shifts the roles and
    renders an agent message as if the user had written it, so the messages are
    kept in order instead.

    Args:
        session: The session payload returned by the ADK backend.

    Returns:
        A list of {"role": "user" | "model", "text": ...} in chronological order.
    """

    messages: list[dict[str, str]] = []

    for event in session.get("events") or []:
        text = extract_event_text(event)
        if not text.strip():
            continue

        role = (event.get("content") or {}).get("role") or "model"
        messages.append({"role": "user" if role == "user" else "model", "text": text})

    return messages


def get_first_user_question(session: dict[str, Any], max_length: int = 40) -> str:
    """Return the beginning of the first user question, for use as a label."""

    for message in get_conversations(session):
        if message["role"] == "user":
            question = " ".join(message["text"].split())
            if len(question) > max_length:
                return f"{question[:max_length - 3]}..."
            return question

    return ""
