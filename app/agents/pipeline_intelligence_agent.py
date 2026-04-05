from typing import List

from app.models.pipeline_record import PipelineRecord
from app.utils.logger import get_logger
from app.utils.time import utc_now_iso

logger = get_logger(__name__)


class PipelineIntelligenceAgent:
    def evaluate_pipeline(self, records: List[PipelineRecord]) -> List[PipelineRecord]:
        logger.info(f"Evaluating {len(records)} pipeline records.")
        evaluated_records = [self._evaluate_record(record) for record in records]
        logger.info("Pipeline evaluation completed.")
        return evaluated_records

    def flag_high_value_deals(
        self,
        records: List[PipelineRecord],
    ) -> List[PipelineRecord]:
        logger.info("Flagging high-value pipeline records.")
        flagged_records = [
            record
            for record in records
            if record.priority == "high" or record.bundle_label == "Full Platform"
        ]
        logger.info(f"Flagged {len(flagged_records)} high-value records.")
        return flagged_records

    def _evaluate_record(self, record: PipelineRecord) -> PipelineRecord:
        updated_record = record
        evaluated_at = utc_now_iso()

        if updated_record.outreach_status == "sent" and updated_record.stage == "new":
            updated_record = updated_record.model_copy(
                update={
                    "stage": "contacted",
                    "next_action": "wait_for_reply",
                    "last_contacted": updated_record.last_contacted or updated_record.last_outreach_at or evaluated_at,
                    "last_updated_at": evaluated_at,
                }
            )

        notes = (updated_record.notes or "").lower()
        if updated_record.stage == "contacted" and "replied" in notes:
            updated_record = updated_record.model_copy(
                update={
                    "stage": "replied",
                    "last_response_at": updated_record.last_response_at or evaluated_at,
                    "last_updated_at": evaluated_at,
                }
            )

        if updated_record.stage == "replied":
            updated_record = updated_record.model_copy(
                update={
                    "next_action": "book_discovery_call",
                    "last_updated_at": evaluated_at,
                }
            )
        elif updated_record.stage == "call_booked":
            updated_record = updated_record.model_copy(
                update={
                    "next_action": "prepare_for_call",
                    "last_updated_at": evaluated_at,
                }
            )
        elif updated_record.stage == "proposal":
            updated_record = updated_record.model_copy(
                update={
                    "next_action": "follow_up_proposal",
                    "last_updated_at": evaluated_at,
                }
            )
        elif updated_record.outreach_status == "not_started":
            updated_record = updated_record.model_copy(
                update={
                    "next_action": "draft_message",
                    "last_updated_at": evaluated_at,
                }
            )
        elif updated_record.outreach_status == "drafted":
            updated_record = updated_record.model_copy(
                update={
                    "next_action": "review_and_send_message",
                    "last_updated_at": evaluated_at,
                }
            )

        return updated_record
