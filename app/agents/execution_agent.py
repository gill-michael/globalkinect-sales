from typing import List

from app.models.execution_task import ExecutionTask
from app.models.pipeline_record import PipelineRecord
from app.utils.logger import get_logger

logger = get_logger(__name__)


class ExecutionAgent:
    def generate_tasks(
        self,
        pipeline_records: List[PipelineRecord],
    ) -> List[ExecutionTask]:
        logger.info(f"Generating execution tasks for {len(pipeline_records)} pipeline records.")
        tasks = [
            task
            for task in (self._build_task(record) for record in pipeline_records)
            if task is not None
        ]
        logger.info(f"Generated {len(tasks)} execution tasks.")
        return tasks

    def _build_task(self, record: PipelineRecord) -> ExecutionTask | None:
        if record.next_action == "draft_message":
            return ExecutionTask(
                lead_reference=record.lead_reference,
                company_name=record.company_name,
                company_canonical=record.company_canonical,
                task_type="draft_message",
                description=(
                    f"Draft the initial outreach for {record.contact_name} at "
                    f"{record.company_name}."
                ),
                priority=record.priority,
                due_in_days=0,
            )

        if record.next_action in {"review_and_send_message", "send_message"}:
            return ExecutionTask(
                lead_reference=record.lead_reference,
                company_name=record.company_name,
                company_canonical=record.company_canonical,
                task_type="send_message",
                description=(
                    f"Review and send the drafted outreach to {record.contact_name} "
                    f"at {record.company_name}."
                ),
                priority=record.priority,
                due_in_days=0,
            )

        if record.next_action == "wait_for_reply":
            return ExecutionTask(
                lead_reference=record.lead_reference,
                company_name=record.company_name,
                company_canonical=record.company_canonical,
                task_type="wait_for_reply",
                description=(
                    f"Monitor for a reply from {record.contact_name} at {record.company_name}."
                ),
                priority=record.priority,
                due_in_days=3,
            )

        if record.next_action == "nudge_message":
            return ExecutionTask(
                lead_reference=record.lead_reference,
                company_name=record.company_name,
                company_canonical=record.company_canonical,
                task_type="nudge_message",
                description=(
                    f"Send a nudge message to {record.contact_name} at {record.company_name} "
                    "to move the conversation forward."
                ),
                priority=record.priority,
                due_in_days=0,
            )

        if record.next_action == "send_follow_up":
            return ExecutionTask(
                lead_reference=record.lead_reference,
                company_name=record.company_name,
                company_canonical=record.company_canonical,
                task_type="follow_up",
                description=(
                    f"Send a follow-up message to {record.contact_name} at {record.company_name}."
                ),
                priority=record.priority,
                due_in_days=0,
            )

        if record.next_action == "escalate_follow_up":
            return ExecutionTask(
                lead_reference=record.lead_reference,
                company_name=record.company_name,
                company_canonical=record.company_canonical,
                task_type="escalate_follow_up",
                description=(
                    f"Escalate the proposal follow-up for {record.company_name} because the "
                    "deal has been inactive."
                ),
                priority="high",
                due_in_days=0,
            )

        if record.next_action == "follow_up_proposal" or record.stage == "proposal":
            return ExecutionTask(
                lead_reference=record.lead_reference,
                company_name=record.company_name,
                company_canonical=record.company_canonical,
                task_type="follow_up",
                description=(
                    f"Follow up on the {record.bundle_label or 'current'} proposal for "
                    f"{record.company_name}."
                ),
                priority=record.priority,
                due_in_days=2,
            )

        if record.next_action == "prepare_for_call" or record.stage == "call_booked":
            return ExecutionTask(
                lead_reference=record.lead_reference,
                company_name=record.company_name,
                company_canonical=record.company_canonical,
                task_type="prepare_call",
                description=(
                    f"Prepare for the scheduled discovery call with {record.contact_name} "
                    f"at {record.company_name}."
                ),
                priority=record.priority,
                due_in_days=1,
            )

        if record.next_action == "book_discovery_call" or record.stage == "replied":
            return ExecutionTask(
                lead_reference=record.lead_reference,
                company_name=record.company_name,
                company_canonical=record.company_canonical,
                task_type="book_call",
                description=(
                    f"Book a discovery call with {record.contact_name} at {record.company_name}."
                ),
                priority=record.priority,
                due_in_days=1,
            )

        return None
