"""ticketsorter: automated ticket categorization, clustering and L1/L2 routing."""

from ticketsorter.models import PipelineOutput, Ticket, TicketResult
from ticketsorter.pipeline import TicketPipeline

__version__ = "0.1.0"
__all__ = ["Ticket", "TicketResult", "PipelineOutput", "TicketPipeline", "__version__"]
