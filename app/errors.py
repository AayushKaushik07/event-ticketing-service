class DomainError(Exception):
    """Base class for errors the application raises on purpose.

    Services raise these; main.py maps them to HTTP status codes. Nothing below
    the controller layer imports fastapi, which is what keeps the services
    testable without a web server.
    """


class EventNotFoundError(DomainError):
    """Raised when an event id does not match any stored event."""

    def __init__(self, event_id: int) -> None:
        self.event_id = event_id
        super().__init__(f"Event '{event_id}' not found")


class NoTicketsAvailableError(DomainError):
    """Raised when someone tries to book a ticket for a sold-out event."""

    def __init__(self, event_id: int) -> None:
        self.event_id = event_id
        super().__init__(f"No tickets available for event '{event_id}'")


class UsernameTakenError(DomainError):
    """Raised when a registration uses a username that already exists."""

    def __init__(self, username: str) -> None:
        self.username = username
        super().__init__(f"Username '{username}' is already taken")


class InvalidCredentialsError(DomainError):
    """Raised on a failed login.

    Deliberately does not say whether the username or the password was wrong:
    distinguishing them lets an attacker enumerate valid usernames.
    """

    def __init__(self) -> None:
        super().__init__("Incorrect username or password")
