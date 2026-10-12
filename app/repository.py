"""All database access lives here.

Two rules hold everywhere in this module:

1. No function commits. The service owns the transaction boundary, because only
   the service knows where a unit of work starts and ends. A repository that
   committed halfway through a booking would release the row lock early and
   reintroduce the oversell bug.
2. No function raises domain errors. Lookups return None and the service decides
   what that means.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Booking, Event, User

# --------------- users ---------------


def get_user_by_username(db: Session, username: str) -> User | None:
    return db.execute(select(User).where(User.username == username)).scalar_one_or_none()


def add_user(db: Session, user: User) -> User:
    db.add(user)
    db.flush()   # assigns the primary key; does NOT commit
    return user


# --------------- events ---------------


def list_events(db: Session) -> list[Event]:
    return list(db.execute(select(Event).order_by(Event.event_date)).scalars())


def get_event(db: Session, event_id: int) -> Event | None:
    return db.get(Event, event_id)


def get_event_for_update(db: Session, event_id: int) -> Event | None:
    """SELECT ... FOR UPDATE — takes an exclusive row lock on this event.

    Any other transaction reaching this line for the same event blocks until the
    caller commits or rolls back. Bookings for *different* events are unaffected,
    which is the whole improvement over a single process-wide lock.
    """
    return db.execute(
        select(Event).where(Event.id == event_id).with_for_update()
    ).scalar_one_or_none()


def add_event(db: Session, event: Event) -> Event:
    db.add(event)
    db.flush()
    return event


def delete_event(db: Session, event: Event) -> None:
    """Bookings are removed by the ON DELETE CASCADE on bookings.event_id, so
    there is no separate delete_bookings_for_event step any more."""
    db.delete(event)


# --------------- bookings ---------------


def add_booking(db: Session, booking: Booking) -> Booking:
    db.add(booking)
    db.flush()
    return booking


def bookings_for_user(db: Session, user_id: int) -> list[Booking]:
    return list(
        db.execute(
            select(Booking)
            .where(Booking.user_id == user_id)
            .order_by(Booking.created_at)
        ).scalars()
    )


def count_bookings_for_event(db: Session, event_id: int) -> int:
    return db.execute(
        select(func.count()).select_from(Booking).where(Booking.event_id == event_id)
    ).scalar_one()
