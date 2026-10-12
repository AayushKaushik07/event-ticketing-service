from sqlalchemy.orm import Session

from app import repository
from app.errors import EventNotFoundError, NoTicketsAvailableError
from app.models import Booking
from app.tickets.ticket_schemas import BookingCount


class TicketService:
    def __init__(self, db: Session) -> None:
        self._db = db

    def book_ticket(self, event_id: int, user_id: int) -> Booking:
        """Book one ticket, holding a row lock across check and write.

        The whole read-check-decrement-insert sequence runs inside one database
        transaction with an exclusive lock on the event row, so two concurrent
        requests for the last ticket cannot both observe it as available.

        Takes user_id rather than a User object: an ORM instance belongs to the
        session that loaded it, and passing one between sessions (as the
        concurrency test does) would be a bug waiting to happen.
        """
        try:
            event = repository.get_event_for_update(self._db, event_id)  # lock acquired
            if event is None:
                raise EventNotFoundError(event_id)
            if event.available_tickets <= 0:
                raise NoTicketsAvailableError(event_id)

            event.available_tickets -= 1
            booking = Booking(event_id=event_id, user_id=user_id)
            repository.add_booking(self._db, booking)
            self._db.commit()                                            # lock released
        except Exception:
            # Explicit rollback so the lock is released immediately rather than
            # when the session is eventually closed.
            self._db.rollback()
            raise

        self._db.refresh(booking)
        return booking

    def list_user_tickets(self, user_id: int) -> list[Booking]:
        return repository.bookings_for_user(self._db, user_id)

    def count_for_event(self, event_id: int) -> BookingCount:
        """Raises EventNotFoundError if the event does not exist.

        `booked` is counted from the bookings rows while `available` comes from
        the counter on the event. They are two views of the same fact, and
        test_counter_matches_booking_rows asserts they agree — that test is the
        drift detector for keeping a counter at all.
        """
        event = repository.get_event(self._db, event_id)
        if event is None:
            raise EventNotFoundError(event_id)
        booked = repository.count_bookings_for_event(self._db, event_id)
        return BookingCount(
            event_id=event_id,
            total_capacity=event.total_capacity,
            booked=booked,
            available=event.available_tickets,
        )
