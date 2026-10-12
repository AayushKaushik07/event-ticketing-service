from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class BookingCreate(BaseModel):
    """Only the event. `user_id` is gone from the request body on purpose: the
    booking is made for whoever the token identifies, so a client can no longer
    book tickets in someone else's name."""

    event_id: int = Field(gt=0)


class BookingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_id: int
    user_id: int
    created_at: datetime


class BookingCount(BaseModel):
    event_id: int
    total_capacity: int
    booked: int
    available: int
