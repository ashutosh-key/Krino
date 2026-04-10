"""HMAC-based pre-interview page token (expires 24h after scheduled_at)."""
from itsdangerous import URLSafeTimedSerializer
from app.config import get_settings

_serializer: URLSafeTimedSerializer | None = None


def _get_serializer() -> URLSafeTimedSerializer:
    global _serializer
    if _serializer is None:
        _serializer = URLSafeTimedSerializer(get_settings().secret_key, salt="pre-interview")
    return _serializer


def generate_pre_interview_token(interview_id: str) -> str:
    return _get_serializer().dumps(interview_id)


def verify_pre_interview_token(token: str, max_age: int = 86400) -> str | None:
    """Returns interview_id if token is valid and not expired, else None."""
    try:
        return _get_serializer().loads(token, max_age=max_age)
    except Exception:
        return None
