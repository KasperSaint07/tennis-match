"""Security utilities for JWT and authentication."""

from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from jose import JWTError, jwt

from app.core.config import get_settings
from app.core.exceptions import InvalidTokenException

settings = get_settings()


def create_jwt_token(
    user_id: UUID,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create JWT token for user.

    Args:
        user_id: UUID of user
        expires_delta: Optional custom expiration time

    Returns:
        JWT token string
    """
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.access_token_expire_minutes)

    expire = datetime.now(timezone.utc) + expires_delta
    data = {
        "sub": str(user_id),
        "exp": expire,
    }

    encoded_jwt = jwt.encode(
        data,
        settings.secret_key,
        algorithm="HS256",
    )
    return encoded_jwt


def verify_jwt_token(token: str) -> UUID:
    """Verify JWT token and extract user ID.

    Args:
        token: JWT token string

    Returns:
        UUID of authenticated user

    Raises:
        InvalidTokenException: If token is invalid or expired
    """
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=["HS256"],
        )
        user_id_str: str = payload.get("sub")
        if user_id_str is None:
            raise InvalidTokenException("Token missing user ID")

        try:
            user_id = UUID(user_id_str)
        except ValueError:
            raise InvalidTokenException("Invalid user ID in token")

        return user_id

    except JWTError as e:
        raise InvalidTokenException(f"Invalid token: {str(e)}")


def verify_telegram_data(init_data: str, bot_token: str) -> dict:
    """Verify Telegram WebApp init data signature.

    For MVP/development: if hash is "test", skip real verification.
    For production: implement full HMAC verification.

    Args:
        init_data: Telegram init data string
        bot_token: Telegram bot token

    Returns:
        Parsed user data

    Raises:
        TelegramVerificationFailedException: If verification fails
    """
    import json
    from urllib.parse import parse_qs

    from app.core.exceptions import TelegramVerificationFailedException

    try:
        # For MVP testing: allow "test" hash
        if "hash=test" in init_data:
            # Parse user data from query string
            parsed = parse_qs(init_data)
            user_data_str = parsed.get("user", [None])[0]
            if not user_data_str:
                raise TelegramVerificationFailedException("Missing user data")
            user_data = json.loads(user_data_str)
            return user_data

        # Production verification
        import hashlib
        import hmac

        data_check_string_parts = []
        for key, value in sorted(parse_qs(init_data).items()):
            if key != "hash":
                data_check_string_parts.append(f"{key}={value[0]}")

        data_check_string = "\n".join(data_check_string_parts)

        # Calculate expected hash
        secret_key = hashlib.sha256(bot_token.encode()).digest()
        expected_hash = hmac.new(
            secret_key,
            data_check_string.encode(),
            hashlib.sha256,
        ).hexdigest()

        # Get actual hash
        parsed = parse_qs(init_data)
        actual_hash = parsed.get("hash", [None])[0]

        if not actual_hash or actual_hash != expected_hash:
            raise TelegramVerificationFailedException("Hash mismatch")

        # Parse user data
        user_data_str = parsed.get("user", [None])[0]
        if not user_data_str:
            raise TelegramVerificationFailedException("Missing user data")

        user_data = json.loads(user_data_str)
        return user_data

    except TelegramVerificationFailedException:
        raise
    except Exception as e:
        raise TelegramVerificationFailedException(f"Verification failed: {str(e)}")
