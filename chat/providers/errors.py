SAFE_PROVIDER_MESSAGE = 'The AI service is temporarily unavailable. Please try again later.'


class LLMUnavailableError(Exception):
    def __init__(self, message: str = SAFE_PROVIDER_MESSAGE, retry_after: int | None = None) -> None:
        self.message = message
        self.retry_after = retry_after
        super().__init__(message)


def _status_code(exc: Exception) -> int | None:
    for attribute in ('status_code', 'code'):
        value = getattr(exc, attribute, None)
        if isinstance(value, int):
            return value
    return None


def _retry_after(exc: Exception) -> int | None:
    response = getattr(exc, 'response', None)
    headers = getattr(response, 'headers', None)
    if not headers:
        return None
    value = headers.get('retry-after') or headers.get('Retry-After')
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def provider_error(exc: Exception) -> LLMUnavailableError:
    retry_after = _retry_after(exc) if _status_code(exc) == 429 else None
    return LLMUnavailableError(SAFE_PROVIDER_MESSAGE, retry_after=retry_after)
