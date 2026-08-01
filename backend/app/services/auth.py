"""Guest authentication use case."""

from dataclasses import dataclass
from hashlib import sha256

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import session_transaction
from app.core.security import TokenService
from app.models.user import User
from app.repositories.users import UserRepository


@dataclass(frozen=True, slots=True)
class GuestLoginResult:
    """Guest authentication result before HTTP serialization."""

    user: User
    access_token: str
    expires_in: int
    created: bool


class AuthService:
    """Create or reuse Guest identities and issue application JWTs."""

    def __init__(self, session: AsyncSession, token_service: TokenService) -> None:
        self._session = session
        self._users = UserRepository(session)
        self._tokens = token_service

    async def login_guest(self, device_id: str | None) -> GuestLoginResult:
        async with session_transaction(self._session):
            if device_id is None:
                user = await self._users.create_guest_without_device()
                created = True
            else:
                device_hash = sha256(device_id.encode("utf-8")).hexdigest()
                user, created = await self._users.create_or_get_guest_by_hash(device_hash)

        return GuestLoginResult(
            user=user,
            access_token=self._tokens.issue(user_id=user.id, role=user.role),
            expires_in=self._tokens.expires_in_seconds,
            created=created,
        )
