import enum
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

# InnoDB + utf8mb4 declared explicitly rather than relying on server defaults,
# so the schema is identical on every machine the migrations run against.
MYSQL_ARGS = {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"}

# BIGINT does not auto-increment on SQLite. The variant exists only so a quick
# throwaway smoke run is possible without a database container; every real run
# (local Docker, CI, deployment) uses MySQL.
PK = BigInteger().with_variant(Integer, "sqlite")


class Role(enum.StrEnum):
    admin = "admin"
    user = "user"


class User(Base):
    """Both admins and normal users live here, separated by `role`.

    One table rather than two: login is a single lookup, `bookings.user_id` has
    an unambiguous foreign key target, and adding a third role later is a new
    enum value instead of a new table plus new join logic.
    """

    __tablename__ = "users"
    __table_args__ = MYSQL_ARGS

    id: Mapped[int] = mapped_column(PK, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    # bcrypt emits 60 chars; 255 leaves room to migrate to argon2 without a
    # schema change.
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[Role] = mapped_column(
        Enum(Role), nullable=False, default=Role.user, server_default=Role.user.value
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    bookings: Mapped[list["Booking"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        # MySQL 8.0.16+ enforces CHECK constraints (MariaDB 10.2+).
        # These catch a corrupt *value*, not a lost update: if concurrent
        # transactions all read available_tickets = 3 and all write 2, the
        # column never goes negative and the constraint never fires while the
        # event is still oversold. Preventing that is the row lock's job, not
        # the constraint's. The constraint is a backstop against a bad UPDATE
        # run by hand, nothing more.
        CheckConstraint("available_tickets >= 0", name="ck_events_available_non_negative"),
        CheckConstraint(
            "available_tickets <= total_capacity", name="ck_events_available_le_capacity"
        ),
        MYSQL_ARGS,
    )

    id: Mapped[int] = mapped_column(PK, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    available_tickets: Mapped[int] = mapped_column(Integer, nullable=False)
    total_capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    # Stored as UTC. MySQL DATETIME carries no timezone, so the convention is
    # enforced by the application: everything written here is already UTC.
    event_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_by: Mapped[int | None] = mapped_column(
        PK, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    bookings: Mapped[list["Booking"]] = relationship(
        back_populates="event", cascade="all, delete-orphan", passive_deletes=True
    )
    creator: Mapped["User | None"] = relationship()


class Booking(Base):
    """One booked ticket. A user may hold several for the same event."""

    __tablename__ = "bookings"
    # No explicit Index() declarations: InnoDB automatically creates an index on
    # every foreign key column, and both lookups here (by event, by user) are on
    # foreign keys. Adding them by hand would duplicate those indexes.
    __table_args__ = MYSQL_ARGS

    id: Mapped[int] = mapped_column(PK, primary_key=True, autoincrement=True)
    event_id: Mapped[int] = mapped_column(
        PK, ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        PK, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    event: Mapped["Event"] = relationship(back_populates="bookings")
    user: Mapped["User"] = relationship(back_populates="bookings")
