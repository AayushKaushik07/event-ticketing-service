from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import require_admin
from app.events.event_schemas import EventCreate, EventOut
from app.events.event_service import EventService
from app.models import User

router = APIRouter(prefix="/events", tags=["events"])


def get_event_service(db: Session = Depends(get_db)) -> EventService:
    return EventService(db)


@router.get("", response_model=list[EventOut])
def list_events(service: EventService = Depends(get_event_service)):
    """List every event. Public — browsing the catalogue needs no account."""
    return service.list_events()


@router.post("", response_model=EventOut, status_code=status.HTTP_201_CREATED)
def create_event(
    payload: EventCreate,
    admin: User = Depends(require_admin),
    service: EventService = Depends(get_event_service),
):
    """Add a new event. Admin only. 403 for a normal user, 401 without a token."""
    return service.create_event(payload, creator_id=admin.id)


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event(
    event_id: int,
    admin: User = Depends(require_admin),
    service: EventService = Depends(get_event_service),
):
    """Delete an event and its bookings. Admin only. 404 if the id is unknown."""
    service.delete_event(event_id)
