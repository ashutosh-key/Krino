"""
Firebase JWT verification.
Handles the HF-Spaces JSON parse quirk (bare newlines in private_key).
"""
from __future__ import annotations
import json
import re
import firebase_admin
from firebase_admin import credentials, auth as firebase_auth
from fastapi import HTTPException, status
from app.config import get_settings

_app: firebase_admin.App | None = None


def _parse_sa_json(raw: str) -> dict:
    """
    Parse Firebase service account JSON that may have bare newlines inside
    the private_key string (common when pasted into env var UIs).
    """
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Escape bare newlines inside JSON string values only
        def _escape_newlines_in_strings(s: str) -> str:
            result = []
            in_string = False
            i = 0
            while i < len(s):
                c = s[i]
                if c == '"' and (i == 0 or s[i - 1] != "\\"):
                    in_string = not in_string
                    result.append(c)
                elif c == "\n" and in_string:
                    result.append("\\n")
                else:
                    result.append(c)
                i += 1
            return "".join(result)

        fixed = _escape_newlines_in_strings(raw)
        return json.loads(fixed)


def _init_firebase() -> None:
    global _app
    if _app is not None:
        return
    settings = get_settings()
    if not settings.firebase_service_account_json:
        return  # auth disabled in dev if no service account provided
    try:
        sa = _parse_sa_json(settings.firebase_service_account_json)
        cred = credentials.Certificate(sa)
        _app = firebase_admin.initialize_app(cred)
    except Exception as exc:
        # Log but don't crash on startup — allows local dev without Firebase
        import structlog
        structlog.get_logger().warning("firebase_init_failed", error=str(exc))


async def verify_firebase_token(token: str) -> dict:
    """
    Verify a Firebase ID token and return the decoded claims.
    Raises 401 if invalid.
    """
    _init_firebase()
    if _app is None:
        # Dev mode: accept any token, return a dummy uid
        return {"uid": "dev-user", "email": "dev@krino.ai"}
    try:
        decoded = firebase_auth.verify_id_token(token, app=_app, check_revoked=True)
        return decoded
    except firebase_auth.RevokedIdTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token revoked")
    except firebase_auth.ExpiredIdTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
