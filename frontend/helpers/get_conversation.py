"""Helper functions"""


def get_conversations(session):
    """Extract and format conversations from session data"""

    conversation_info = []

    for conversation in session["events"]:
        if "text" in conversation["content"]["parts"][0]:
            conversation_info.append({
                conversation["content"]["role"]: conversation["content"]["parts"][0]["text"]
            })

    merged = {}
    for i in range(0, len(conversation_info), 2):
        if i + 1 < len(conversation_info):
            merged[i // 2] = {**conversation_info[i], **conversation_info[i + 1]}
        else:
            merged[i // 2] = conversation_info[i]

    return merged


def get_first_user_question(session):
    """Return the first 20 chars from the
    first user question in a session"""
    if session["events"]:
        if "text" in session["events"][0]["content"]["parts"][0]:
            return session["events"][0]["content"]["parts"][0]["text"][0:20]


