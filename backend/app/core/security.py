"""JWT creation and validation for Guest authentication."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from uuid import UUID

import jwt
from jwt import InvalidTokenError

from app.core.config import Settings
from app.core.exceptions import AppError


@dataclass(frozen=True, slots=True)
class AuthenticatedUser:
    """Trusted identity derived from a verified JWT and active database user."""

    id: UUID
    display_name: str | None
    role: str


class TokenService:
    """Issue and verify application-owned HS256 access tokens."""

    def __init__(self, settings: Settings) -> None:
        if settings.jwt_secret is None:
            raise AppError(
                code="AUTH_CONFIGURATION_ERROR",
                message="authentication is not configured",
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            )
        self._secret = settings.jwt_secret.get_secret_value()
        self._algorithm = settings.jwt_algorithm
        self._expire_minutes = settings.jwt_expire_minutes
        self._issuer = settings.jwt_issuer

    @property
    def expires_in_seconds(self) -> int:
        """Return the configured token lifetime in seconds."""
        return self._expire_minutes * 60

    def issue(self, *, user_id: UUID, role: str) -> str:
        """Create one signed access token for an authenticated user."""
        issued_at = datetime.now(UTC)
        payload = {
            "sub": str(user_id),
            "role": role,
            "iss": self._issuer,
            "iat": issued_at,
            "exp": issued_at + timedelta(minutes=self._expire_minutes),
        }
        return jwt.encode(payload, self._secret, algorithm=self._algorithm)

    def verify(self, token: str) -> tuple[UUID, str]:
        """Verify a token and return its trusted subject and role claims."""
        try:
            payload = jwt.decode(
                token,
                self._secret,
                algorithms=[self._algorithm],
                issuer=self._issuer,
                options={"require": ["sub", "role", "iss", "iat", "exp"]},
            )
            user_id = UUID(str(payload["sub"]))
            role = str(payload["role"])
            if role not in {"user", "dev"}:
                raise ValueError("unsupported role")
        except (InvalidTokenError, KeyError, TypeError, ValueError) as exc:
            raise AppError(
                code="AUTH_INVALID_TOKEN",
                message="invalid or expired access token",
                status_code=HTTPStatus.UNAUTHORIZED,
            ) from exc
        return user_id, role
