"""Tool schemas for the manual recruiter-message-drafting agent loop."""

TOOLS = [
    {
        "name": "search_similar_messages",
        "description": (
            "Searches your archive of previously sent recruiter messages for ones targeting "
            "similar roles or technologies. Use this BEFORE drafting. You can call this "
            "multiple times with different queries."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
    {
        "name": "search_cv_highlights",
        "description": (
            "Searches your CV for achievements most relevant to a given requirement from the offer."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"requirement": {"type": "string"}},
            "required": ["requirement"],
        },
    },
    {
        "name": "save_draft",
        "description": "Saves the final draft recruiter message. Call this exactly ONCE.",
        "input_schema": {
            "type": "object",
            "properties": {
                "body": {"type": "string"},
                "tone": {"type": "string"},
                "based_on": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["body", "tone", "based_on"],
        },
    },
]
