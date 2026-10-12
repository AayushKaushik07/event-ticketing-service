from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import get_current_user, require_admin
from app.models import User
from app.tickets.ticket_schemas import BookingCount, BookingCreate, BookingOut
from app.tickets.ticket_service import TicketService

router = APIRouter(prefix="/tickets", tags=["tickets"])


def get_ticket_service(db: Session = Depends(get_db)) -> TicketService:
    return TicketService(db)


@router.post("", response_model=BookingOut, status_code=status.HTTP_201_CREATED)
def book_ticket(
    payload: BookingCreate,
    current_user: User = Depends(get_current_user),
    service: TicketService = Depends(get_ticket_service),
):
    """Book one ticket for the authenticated user.

    404 if the event does not exist, 400 if it is sold out, 401 without a token.
    Admins can book too — the restriction is on who may *create* events.
    """
    return service.book_ticket(payload.event_id, current_user.id)


@router.get("/me", response_model=list[BookingOut])
def list_my_tickets(
    current_user: User = Depends(get_current_user),
    service: TicketService = Depends(get_ticket_service),
):
    """Every ticket booked by the caller. A user can only ever see their own."""
    return service.list_user_tickets(current_user.id)


@router.get("/count", response_model=BookingCount)
def get_booking_count(
    event_id: int,
    admin: User = Depends(require_admin),
    service: TicketService = Depends(get_ticket_service),
):
    """How many tickets are booked for one event. Admin only."""
    return service.count_for_event(event_id)
