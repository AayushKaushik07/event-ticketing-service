"""The test that justifies the row lock.

A naive version of this test - spawn N threads, call book_ticket, assert one
wins - passes even with the lock removed, because each booking completes in
under a millisecond and the threads never actually overlap. A concurrency test
that passes against broken code is worse than no test at all.

Two things make the race real and repeatable here:

1. A threading.Barrier, so all threads enter the transaction at the same instant
   instead of trickling into a thread pool.
2. A monkeypatched delay between the availability read and the write, which
   widens the window an unlucky production request could hit anyway. The delay
   is injected by the test; no production code knows about it.

With the lock, threads queue on the event row and the delay costs wall-clock
time but changes nothing. Without it, every thread reads the same stale
availability and the event oversells.
"""

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import pytest

from app import repository
from app.errors import NoTicketsAvailableError
from app.models import Booking, Event, Role, User
from app.security import hash_password
from app.tickets.ticket_service import TicketService
from tests.conftest import TestingSession

THREADS = 10
WRITE_DELAY_SECONDS = 0.25


@pytest.fixture
def slow_write(monkeypatch):
    """Widen the gap between reading availability and writing the booking."""
    original = repository.add_booking

    def delayed(db, booking):
        time.sleep(WRITE_DELAY_SECONDS)
        return original(db, booking)

    monkeypatch.setattr(repository, "add_booking", delayed)


def _seed(db, seats: int) -> tuple[int, list[int]]:
    users = [
        User(
            username=f"racer{i}",
            password_hash=hash_password("password123"),
            role=Role.user,
        )
        for i in range(THREADS)
    ]
    db.add_all(users)
    event = Event(
        name="Last Ticket",
        available_tickets=seats,
        total_capacity=seats,
        event_date=datetime(2027, 1, 4, 19, 30),
    )
    db.add(event)
    db.commit()
    return event.id, [u.id for u in users]


def _race(event_id: int, user_ids: list[int]) -> list[str]:
    """Every thread gets its own Session - SQLAlchemy sessions are not
    thread-safe, and sharing one would make the result meaningless."""
    barrier = threading.Barrier(THREADS)

    def attempt(user_id: int) -> str:
        session = TestingSession()
        try:
            barrier.wait(timeout=30)
            TicketService(session).book_ticket(event_id, user_id)
            return "booked"
        except NoTicketsAvailableError:
            return "sold_out"
        finally:
            session.close()

    with ThreadPoolExecutor(max_workers=THREADS) as pool:
        return list(pool.map(attempt, user_ids))


def test_last_ticket_is_sold_exactly_once(db, slow_write):
    event_id, user_ids = _seed(db, seats=1)

    results = _race(event_id, user_ids)

    assert results.count("booked") == 1
    assert results.count("sold_out") == THREADS - 1


def test_no_overselling_with_partial_capacity(db, slow_write):
    """Ten threads, four tickets. Exactly four win and the counter lands on 0."""
    event_id, user_ids = _seed(db, seats=4)

    results = _race(event_id, user_ids)

    assert results.count("booked") == 4
    assert results.count("sold_out") == THREADS - 4

    db.expire_all()
    assert db.get(Event, event_id).available_tickets == 0
    assert repository.count_bookings_for_event(db, event_id) == 4


def test_counter_and_rows_agree_after_a_race(db, slow_write):
    """The invariant that makes keeping a counter safe."""
    event_id, user_ids = _seed(db, seats=3)

    _race(event_id, user_ids)

    db.expire_all()
    event = db.get(Event, event_id)
    rows = db.query(Booking).filter_by(event_id=event_id).count()
    assert rows + event.available_tickets == event.total_capacity
