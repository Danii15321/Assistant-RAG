from uuid import UUID, uuid4

from sqlalchemy import Engine, text

from app.models.user import UserProfile
from app.services.identity import VerifiedIdentity


class IdentityRepository:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def session_is_active(self, identity: VerifiedIdentity) -> bool:
        with self.engine.connect() as connection:
            return bool(
                connection.execute(
                    text(
                        "SELECT EXISTS (SELECT 1 FROM auth_session "
                        'WHERE id = :sid AND "userId" = :subject AND "expiresAt" > now())'
                    ),
                    {"sid": identity.session_id, "subject": identity.subject},
                ).scalar_one()
            )

    def current_user(self, subject: str) -> UserProfile:
        with self.engine.begin() as connection:
            row = (
                connection.execute(
                    text(
                        "INSERT INTO users (id, auth_user_id) VALUES (:id, :subject) "
                        "ON CONFLICT (auth_user_id) DO UPDATE SET auth_user_id = :subject "
                        "RETURNING id, created_at"
                    ),
                    {"id": uuid4(), "subject": subject},
                )
                .mappings()
                .one()
            )
            return UserProfile.model_validate(dict(row))

    def owned_user(self, subject: str, user_id: UUID) -> UserProfile | None:
        with self.engine.connect() as connection:
            row = (
                connection.execute(
                    text(
                        "SELECT id, created_at FROM users "
                        "WHERE id = :id AND auth_user_id = :subject"
                    ),
                    {"id": user_id, "subject": subject},
                )
                .mappings()
                .one_or_none()
            )
            return None if row is None else UserProfile.model_validate(dict(row))
