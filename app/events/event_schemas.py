from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EventCreate(BaseModel):
    """Fields an admin provides when creating a new event."""

    name: str = Field(min_length=1, max_length=200)
    available_tickets: int = Field(gt=0, le=1_000_000, description="Starting capacity.")
    event_date: datetime = Field(description="ISO 8601, e.g. 2027-01-04T19:30:00Z")

    @field_validator("event_date")
    @classmethod
    def must_be_in_the_future(cls, value: datetime) -> datetime:
        """Normalise to naive UTC and reject past dates.

        MySQL DATETIME stores no timezone, so the value is converted to UTC here
        and stored naive. A tz-naive input is assumed to already be UTC.
        """
        if value.tzinfo is not None:
            value = value.astimezone(UTC).replace(tzinfo=None)
        if value <= datetime.now(UTC).replace(tzinfo=None):
            raise ValueError("event_date must be in the future")
        return value


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    available_tickets: int
    total_capacity: int
    event_date: datetime
    created_at: datetime
