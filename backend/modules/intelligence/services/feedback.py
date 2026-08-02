import logging

from backend.modules.intelligence.schemas.intelligence_dto import FeedbackEventDTO


class FeedbackProcessor:
    def __init__(self):
        self.logger = logging.getLogger("feedback_processor")

    async def ingest_feedback(self, event: FeedbackEventDTO):
        # In a real system, this would write to a timeseries DB or message queue
        self.logger.info(
            f"Ingested feedback for query {event.query_id}: {event.feedback_type}"
        )
        return True
