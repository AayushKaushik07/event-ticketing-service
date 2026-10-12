from sqlalchemy.orm import Session

from app import repository
from app.errors import EventNotFoundError
from app.events.event_schemas import EventCreate
from app.models import Event


class EventService:
    """Constructed per request with the request's session.

    The in-memory version injected a shared repository singleton into a
    module-level service instance. A database session cannot be shared that way
    (it is per-request and not thread-safe), so the session is what gets injected
    now and the service instance is created per request by a FastAPI dependency.
    """

    def __init__(self, db: Session) -> None:
        self._db = db

    def list_events(self) -> list[Event]:
        return repository.list_events(self._db)

    def create_event(self, payload: EventCreate, creator_id: int) -> Event:
        # The service builds the entity and sets the starting capacity; the
        # repository only stores what it is given. The id now comes from the
        # database (AUTO_INCREMENT) instead of uuid4.
        event = Event(
            name=payload.name,
            available_tickets=payload.available_tickets,
            total_capacity=payload.available_tickets,
            event_date=payload.event_date,
            created_by=creator_id,
        )
        repository.add_event(self._db, event)
        self._db.commit()
        self._db.refresh(event)
        return event

    def delete_event(self, event_id: int) -> None:
        """Delete an event and, by FK cascade, its bookings.

        Raises EventNotFoundError if the id is unknown — deletes are NOT
        idempotent here. This is an admin-only operation, and telling an admin
        that the thing they tried to delete does not exist is more useful than
        silently succeeding.
        """
        event = repository.get_event(self._db, event_id)
        if event is None:
            raise EventNotFoundError(event_id)
        repository.delete_event(self._db, event)
        self._db.commit()
