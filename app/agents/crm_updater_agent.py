from typing import List

from app.models.lead import Lead
from app.models.outreach_message import OutreachMessage
from app.models.pipeline_record import OutreachStatus, PipelineRecord, PipelineStage
from app.models.solution_recommendation import SolutionRecommendation
from app.utils.time import utc_now_iso
from app.utils.logger import get_logger
from app.utils.target_markets import country_label

logger = get_logger(__name__)


class CRMUpdaterAgent:
    def create_pipeline_records_with_solution(
        self,
        leads: List[Lead],
        solution_recommendations: List[SolutionRecommendation],
    ) -> List[PipelineRecord]:
        if len(leads) != len(solution_recommendations):
            raise ValueError("Lead and solution recommendation counts must match.")

        logger.info(f"Creating {len(leads)} solution-aligned pipeline records.")
        records = [
            PipelineRecord(
                lead_reference=solution_recommendation.lead_reference,
                company_name=lead.company_name,
                company_canonical=lead.company_canonical,
                contact_name=lead.contact_name,
                lead_type=lead.lead_type or "unknown",
                target_country=lead.target_country or "unknown",
                score=lead.score or 1,
                priority=lead.priority or "low",
                sales_motion=solution_recommendation.sales_motion,
                primary_module=solution_recommendation.primary_module,
                bundle_label=solution_recommendation.bundle_label,
                recommended_modules=solution_recommendation.recommended_modules,
                stage="new",
                outreach_status="not_started",
                next_action=self._default_next_action_for_outreach_status("not_started"),
            )
            for lead, solution_recommendation in zip(leads, solution_recommendations)
        ]
        logger.info("Solution-aligned pipeline records created.")
        return records

    def create_pipeline_records(
        self,
        leads: List[Lead],
        outreach_messages: List[OutreachMessage] | None = None,
    ) -> List[PipelineRecord]:
        if outreach_messages is not None and len(leads) != len(outreach_messages):
            raise ValueError("Lead and outreach message counts must match.")

        logger.info(f"Creating {len(leads)} pipeline records.")
        if outreach_messages is None:
            records = [
                PipelineRecord(
                    lead_reference=self._build_lead_reference(lead),
                    company_name=lead.company_name,
                    company_canonical=lead.company_canonical,
                    contact_name=lead.contact_name,
                    lead_type=lead.lead_type or "unknown",
                    target_country=lead.target_country or "unknown",
                    score=lead.score or 1,
                    priority=lead.priority or "low",
                    sales_motion=None,
                    primary_module=None,
                    bundle_label=None,
                    recommended_modules=None,
                    stage="new",
                    outreach_status="not_started",
                    next_action=self._default_next_action_for_outreach_status("not_started"),
                )
                for lead in leads
            ]
        else:
            records = [
                PipelineRecord(
                    lead_reference=message.lead_reference,
                    company_name=lead.company_name,
                    company_canonical=lead.company_canonical,
                    contact_name=lead.contact_name,
                    lead_type=lead.lead_type or "unknown",
                    target_country=lead.target_country or "unknown",
                    score=lead.score or 1,
                    priority=lead.priority or "low",
                    sales_motion=None,
                    primary_module=None,
                    bundle_label=None,
                    recommended_modules=None,
                    stage="new",
                    outreach_status="drafted",
                    next_action=self._default_next_action_for_outreach_status("drafted"),
                )
                for lead, message in zip(leads, outreach_messages)
            ]
        logger.info("Pipeline records created.")
        return records

    def update_stage(
        self,
        record: PipelineRecord,
        new_stage: PipelineStage,
    ) -> PipelineRecord:
        logger.info(
            f"Updating stage for {record.lead_reference} from {record.stage} to {new_stage}."
        )
        updated_at = utc_now_iso()
        update_payload = {
            "stage": new_stage,
            "next_action": self._default_next_action_for_stage(new_stage),
            "last_updated_at": updated_at,
        }
        if new_stage == "contacted":
            update_payload["last_contacted"] = updated_at
        if new_stage == "replied":
            update_payload["last_response_at"] = updated_at
        return record.model_copy(update=update_payload)

    def update_outreach_status(
        self,
        record: PipelineRecord,
        new_status: OutreachStatus,
    ) -> PipelineRecord:
        logger.info(
            f"Updating outreach status for {record.lead_reference} from {record.outreach_status} to {new_status}."
        )
        updated_at = utc_now_iso()
        update_payload = {
            "outreach_status": new_status,
            "next_action": self._default_next_action_for_outreach_status(new_status),
            "last_updated_at": updated_at,
        }
        if new_status == "sent":
            update_payload["last_outreach_at"] = updated_at
            update_payload["last_contacted"] = updated_at
        if new_status == "replied":
            update_payload["last_response_at"] = updated_at
            update_payload["last_contacted"] = updated_at
        return record.model_copy(update=update_payload)

    def set_next_action(self, record: PipelineRecord, action: str) -> PipelineRecord:
        logger.info(f"Setting next action for {record.lead_reference} to {action}.")
        updated_at = utc_now_iso()
        return record.model_copy(
            update={
                "next_action": action,
                "last_updated_at": updated_at,
            }
        )

    def log_activity(self, record: PipelineRecord, note: str) -> PipelineRecord:
        logger.info(f"Logging activity for {record.lead_reference}.")
        existing_notes = record.notes or ""
        updated_notes = note if not existing_notes else f"{existing_notes}\n{note}"
        updated_at = utc_now_iso()
        return record.model_copy(
            update={
                "notes": updated_notes,
                "last_updated_at": updated_at,
            }
        )

    def _default_next_action_for_stage(self, stage: PipelineStage) -> str:
        actions = {
            "new": "review_and_send_message",
            "contacted": "wait_for_reply",
            "replied": "book_discovery_call",
            "call_booked": "prepare_for_call",
            "proposal": "follow_up_proposal",
            "closed": "no_further_action",
        }
        return actions[stage]

    def _default_next_action_for_outreach_status(
        self,
        outreach_status: OutreachStatus,
    ) -> str:
        actions = {
            "not_started": "draft_message",
            "drafted": "review_and_send_message",
            "approved": "send_message",
            "sent": "wait_for_reply",
            "replied": "review_and_send_reply",
        }
        return actions[outreach_status]

    def _build_lead_reference(self, lead: Lead) -> str:
        parts = [
            lead.company_name,
            lead.contact_name,
            self._country_label(lead.target_country),
            lead.lead_type or "unknown",
        ]
        return "|".join(parts)

    def _country_label(self, target_country: str | None) -> str:
        return country_label(target_country)
