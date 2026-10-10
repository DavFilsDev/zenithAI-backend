from typing import Optional, Sequence

from django.conf import settings

from .base import ChatMessage

CHARS_PER_TOKEN = 4


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // CHARS_PER_TOKEN)


def windowed_history(
    history: Sequence[ChatMessage],
    budget: Optional[int] = None,
) -> Sequence[ChatMessage]:
    if budget is None:
        budget = settings.LLM_PROMPT_BUDGET
    window = []
    used = 0
    for item in reversed(history):
        cost = estimate_tokens(item['content']) + 1
        if used + cost > budget:
            break
        window.append(item)
        used += cost
    return list(reversed(window))