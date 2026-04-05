from datetime import datetime
from typing import List

from app.models.pipeline_record import PipelineRecord
from app.utils.logger import get_logger
from app.utils.time import parse_iso_datetime, utc_now

logger = get_logger(__name__)


class LifecycleAgent:
    def evaluate_lifecycle(
        self,
        records: List[PipelineRecord],
        reference_time: datetime | None = None,
    ) -> List[PipelineRecord]:
        effective_time = reference_time or utc_now()
        logger.info(f"Evaluating lifecycle state for {len(records)} pipeline records.")
        evaluated_records = [
            self._evaluate_record(record, effective_time)
            for record in records
        ]
        logger.info("Lifecycle evaluation completed.")
        return evaluated_records

    def _evaluate_record(
        self,
        record: PipelineRecord,
        reference_time: datetime,
    ) -> PipelineRecord:
        if record.stage == "proposal" and self._is_stale(
            record.last_updated_at,
            reference_time,
            5,
        ):
            return self._update_next_action(
                record,
                "escalate_follow_up",
                reference_time,
            )

        if (
            record.stage == "contacted"
            and record.last_response_at is None
            and self._is_stale(record.last_contacted or record.last_outreach_at, reference_time, 2)
        ):
            return self._update_next_action(record, "nudge_message", reference_time)

        if (
            record.outreach_status == "sent"
            and record.last_response_at is None
            and self._is_stale(record.last_outreach_at or record.last_contacted, reference_time, 3)
        ):
            return self._update_next_action(record, "send_follow_up", reference_time)

        return record

    def _update_next_action(
        self,
        record: PipelineRecord,
        next_action: str,
        reference_time: datetime,
    ) -> PipelineRecord:
        return record.model_copy(
            update={
                "next_action": next_action,
                "last_updated_at": reference_time.isoformat(),
            }
        )

    def _is_stale(
        self,
        timestamp_value: str | None,
        reference_time: datetime,
        threshold_days: int,
    ) -> bool:
        parsed_timestamp = parse_iso_datetime(timestamp_value)
        if parsed_timestamp is None:
            return False
        age = reference_time - parsed_timestamp
        return age.days >= threshold_days
