"""FastAPI service.

POST /v1/classify        single ticket -> category + L1/L2 + priority   (real-time, for webhooks)
POST /v1/classify/batch  many tickets, classification only
POST /v1/cluster         many tickets -> clusters + results             (needs >= ~6 tickets)
GET  /healthz            liveness/readiness
"""

from __future__ import annotations

import hmac
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from ticketsorter import __version__
from ticketsorter.config import Settings
from ticketsorter.models import PipelineOutput, Ticket, TicketResult
from ticketsorter.pipeline import TicketPipeline

log = logging.getLogger("ticketsorter.api")


class BatchRequest(BaseModel):
    tickets: list[Ticket] = Field(min_length=1)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    logging.basicConfig(level=settings.log_level)
    state: dict[str, TicketPipeline] = {}

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        state["pipeline"] = TicketPipeline(settings)  # loads the model once at startup
        log.info("Pipeline ready (backend=%s)", settings.embedding_backend)
        yield
        state.clear()

    app = FastAPI(title="Ticket Categorizer", version=__version__, lifespan=lifespan)

    def require_key(x_api_key: str | None = Header(default=None)) -> None:
        if settings.api_key and not (x_api_key and hmac.compare_digest(x_api_key, settings.api_key)):
            raise HTTPException(status_code=401, detail="invalid or missing X-API-Key")

    def check_size(tickets: list[Ticket]) -> None:
        if len(tickets) > settings.max_batch_size:
            raise HTTPException(413, f"max {settings.max_batch_size} tickets per request")

    @app.get("/healthz")
    def healthz() -> dict:
        return {"status": "ok", "version": __version__, "ready": "pipeline" in state}

    @app.post("/v1/classify", response_model=TicketResult, dependencies=[Depends(require_key)])
    def classify(ticket: Ticket) -> TicketResult:
        return state["pipeline"].classify([ticket])[0]

    @app.post("/v1/classify/batch", response_model=list[TicketResult], dependencies=[Depends(require_key)])
    def classify_batch(req: BatchRequest) -> list[TicketResult]:
        check_size(req.tickets)
        return state["pipeline"].classify(req.tickets)

    @app.post("/v1/cluster", response_model=PipelineOutput, dependencies=[Depends(require_key)])
    def cluster(req: BatchRequest) -> PipelineOutput:
        check_size(req.tickets)
        return state["pipeline"].run(req.tickets)

    return app
