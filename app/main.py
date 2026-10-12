import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.auth import auth_controller
from app.db import engine
from app.errors import (
    EventNotFoundError,
    InvalidCredentialsError,
    NoTicketsAvailableError,
    UsernameTakenError,
)
from app.events import event_controller
from app.tickets import ticket_controller

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Event Ticketing Service",
    description=(
        "Ticket booking API with JWT authentication, role-based access control "
        "and concurrency-safe seat allocation on MySQL."
    ),
    version="2.0.0",
)

# --------------- Feature Controllers ---------------
app.include_router(auth_controller.router)
app.include_router(event_controller.router)
app.include_router(ticket_controller.router)


@app.get("/health", tags=["meta"])
def health_check():
    """Liveness plus a dependency check.

    Used by the Docker healthcheck and, later, by Kubernetes or Azure probes.
    Returns 503 rather than 200 when the database is unreachable, so an
    orchestrator can stop routing traffic to an instance that cannot serve.
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        logger.exception("Health check failed: database unreachable")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "degraded", "database": "down"},
        )
    return {"status": "ok", "database": "up"}


# --------------- Error handling ---------------
# Services raise plain domain errors and they are translated into HTTP responses
# here, so there is only one place to look for the status codes.


@app.exception_handler(EventNotFoundError)
async def handle_event_not_found(request: Request, exc: EventNotFoundError):
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(exc)}
    )


@app.exception_handler(NoTicketsAvailableError)
async def handle_no_tickets(request: Request, exc: NoTicketsAvailableError):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST, content={"detail": str(exc)}
    )


@app.exception_handler(UsernameTakenError)
async def handle_username_taken(request: Request, exc: UsernameTakenError):
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT, content={"detail": str(exc)}
    )


@app.exception_handler(InvalidCredentialsError)
async def handle_invalid_credentials(request: Request, exc: InvalidCredentialsError):
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"detail": str(exc)},
        headers={"WWW-Authenticate": "Bearer"},
    )


@app.exception_handler(Exception)
async def handle_unexpected(request: Request, exc: Exception):
    """Last resort so an unexpected error still comes back as JSON.

    logger.exception writes the full traceback to the server log while the
    client gets a generic message — internal details in an error response are an
    information leak.
    """
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
