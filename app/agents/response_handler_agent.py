"""Response handler agent — classifies prospect replies and drafts next-step messages.

Runs as part of the main sourcing cycle (after the feedback index step).
Shadow mode classifies and drafts but skips all writes.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from app.agents.crm_updater_agent import CRMUpdaterAgent
from app.models.execution_task import ExecutionTask
from app.models.operator_console import OutreachQueueRecord
from app.models.pipeline_record import PipelineRecord
from app.services.anthropic_service import AnthropicService
from app.services.notion_service import NotionService
from app.services.supabase_service import SupabaseService
from app.utils.logger import get_logger
from app.utils.time import utc_now_iso

logger = get_logger(__name__)


VALID_CLASSIFICATIONS = {
    "positive",
    "objection",
    "negative",
    "out_of_office",
    "neutral",
    "request_for_info",
}

CLASSIFICATION_TO_STAGE = {
    "positive": "call_booked",
    "objection": "contacted",
    "negative": "closed",
    "out_of_office": "contacted",
    "neutral": "contacted",
    "request_for_info": "replied",
}

CLASSIFICATION_TO_QUEUE_STATUS = {
    "positive": "drafted",
    "objection": "drafted",
    "negative": "closed",
    "out_of_office": "hold",
    "neutral": "drafted",
    "request_for_info": "drafted",
}

CLASSIFICATION_TO_TASK_PRIORITY = {
    "positive": "high",
    "objection": "high",
    "request_for_info": "high",
    "neutral": "low",
    "negative": "none",
    "out_of_office": "none",
}

CLASSIFICATION_TO_DUE_IN_DAYS = {
    "positive": 0,
    "objection": 0,
    "request_for_info": 0,
    "neutral": 0,
    "negative": 0,
    "out_of_office": 7,
}

SYSTEM_PROMPT = (
    "You are a sales reply classifier for Global Kinect, a multi-country payroll, "
    "HRIS, and EOR platform serving MENA and European markets."
)


@dataclass
class ResponseHandlerResult:
    reviewed_count: int = 0
    classified_count: int = 0
    drafted_count: int = 0
    skipped_count: int = 0
    failed_count: int = 0
    by_classification: dict[str, int] = field(default_factory=dict)

    def summary(self) -> str:
        base = (
            f"reviewed={self.reviewed_count}, classified={self.classified_count}, "
            f"drafted={self.drafted_count}, skipped={self.skipped_count}, "
            f"failed={self.failed_count}"
        )
        if not self.by_classification:
            return base
        breakdown = ", ".join(
            f"{label}={count}" for label, count in sorted(self.by_classification.items())
        )
        return f"{base} | {breakdown}"


class ResponseHandlerAgent:
    def __init__(
        self,
        notion_service: NotionService,
        anthropic_service: AnthropicService,
        supabase_service: SupabaseService,
        crm_updater_agent: CRMUpdaterAgent,
    ) -> None:
        self.notion_service = notion_service
        self.anthropic_service = anthropic_service
        self.supabase_service = supabase_service
        self.crm_updater_agent = crm_updater_agent
        self._reply_property_checked = False

    def is_configured(self) -> bool:
        queue_check = getattr(
            self.notion_service, "is_outreach_queue_configured", None
        )
        if queue_check is None or not queue_check():
            return False
        anthropic_check = getattr(self.anthropic_service, "is_configured", None)
        return anthropic_check is not None and anthropic_check()

    def process_replies(
        self,
        limit: int = 50,
        shadow_mode: bool = False,
    ) -> ResponseHandlerResult:
        result = ResponseHandlerResult()
        if not self.is_configured():
            logger.info("Response handler is not configured. Skipping reply processing.")
            return result

        self._ensure_reply_property()

        try:
            replied_records = self.notion_service.fetch_outreach_queue_replied_records(
                limit=limit,
            )
        except Exception as exc:
            logger.warning("Could not fetch replied outreach records: %s", exc)
            return result

        if not replied_records:
            logger.info("No replied outreach records with Reply content found.")
            return result

        for record, reply_text in replied_records:
            result.reviewed_count += 1
            try:
                classification = self._classify(reply_text)
            except Exception as exc:
                logger.warning(
                    "Classification failed for %s: %s",
                    record.lead_reference or record.page_id,
                    exc,
                )
                result.failed_count += 1
                continue

            if classification is None:
                result.failed_count += 1
                continue

            label = classification["classification"]
            result.classified_count += 1
            result.by_classification[label] = result.by_classification.get(label, 0) + 1

            drafted_message = self._draft_response(record, classification)
            if drafted_message:
                result.drafted_count += 1

            event = self._build_response_event(
                record, reply_text, classification, drafted_message
            )

            if shadow_mode:
                self._print_shadow_output(record, classification, drafted_message)
                print(f"[shadow] RESPONSE EVENT: {json.dumps(event)}")
                continue

            try:
                self._apply_updates(record, reply_text, classification, drafted_message)
            except Exception as exc:
                logger.warning(
                    "Failed to apply response updates for %s: %s",
                    record.lead_reference or record.page_id,
                    exc,
                )
                result.failed_count += 1
                continue

            if self.supabase_service.is_configured():
                try:
                    self.supabase_service.insert_response_events([event])
                except Exception as exc:
                    logger.warning(
                        "Response event persist failed for %s: %s",
                        record.lead_reference or record.page_id,
                        exc,
                    )

        logger.info("Response handler completed with %s", result.summary())
        return result

    def _ensure_reply_property(self) -> None:
        if self._reply_property_checked:
            return
        try:
            self.notion_service.ensure_outreach_queue_reply_property()
        except Exception as exc:
            logger.warning("Could not ensure Reply property on outreach queue: %s", exc)
        self._reply_property_checked = True

    def _classify(self, reply_text: str) -> dict[str, Any] | None:
        user_prompt = (
            "Classify this reply into exactly one category: "
            "positive, objection, negative, out_of_office, neutral, request_for_info\n\n"
            "Definitions:\n"
            "positive — interested, wants more info, asks for meeting, asks for pricing\n"
            "objection — raises concern but has not closed the door (timing, budget, "
            "incumbent, not decision maker)\n"
            "negative — not interested, unsubscribe, wrong person\n"
            "out_of_office — automated OOO message\n"
            "neutral — acknowledged but no clear intent\n"
            "request_for_info — asks a specific product question\n\n"
            f"Reply text: {reply_text}\n\n"
            'Return JSON only, no preamble: '
            '{"classification": "<value>", "summary": "<one sentence>", '
            '"key_concern": "<if objection else null>"}'
        )
        response = self.anthropic_service.client.messages.create(
            model=self.anthropic_service.model,
            max_tokens=400,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        text_blocks = [
            block.text
            for block in response.content
            if getattr(block, "type", None) == "text"
        ]
        if not text_blocks:
            return None
        parsed = self._parse_json(("\n".join(text_blocks)).strip())
        if not parsed:
            return None
        label = (parsed.get("classification") or "").strip().lower()
        if label not in VALID_CLASSIFICATIONS:
            logger.warning("Anthropic returned unknown classification %r", label)
            return None
        parsed["classification"] = label
        return parsed

    def _parse_json(self, text: str) -> dict[str, Any] | None:
        candidate = text.strip()
        if candidate.startswith("```"):
            candidate = candidate.strip("`")
            if candidate.lower().startswith("json"):
                candidate = candidate[4:]
            candidate = candidate.strip()
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start == -1 or end <= start:
            return None
        try:
            result = json.loads(candidate[start : end + 1])
        except json.JSONDecodeError:
            return None
        return result if isinstance(result, dict) else None

    def _draft_response(
        self,
        record: OutreachQueueRecord,
        classification: dict[str, Any],
    ) -> str:
        label = classification["classification"]
        country = record.target_country or "your market"
        contact_first_name = self._first_name(record.contact_name)

        if label == "positive":
            return (
                f"Great to hear from you{(', ' + contact_first_name) if contact_first_name else ''}. "
                f"Happy to set up a quick call to walk through how Global Kinect handles "
                f"{country}. What does your calendar look like this week or next?"
            )

        if label == "objection":
            key_concern = classification.get("key_concern") or ""
            return self._draft_objection_response(record, key_concern)

        if label == "request_for_info":
            return self._draft_request_for_info_response(record, country)

        if label == "neutral":
            return (
                f"Just checking this landed — happy to share a quick overview of how "
                f"Global Kinect works for {country} if useful."
            )

        # negative and out_of_office produce no outbound message
        return ""

    def _draft_objection_response(
        self,
        record: OutreachQueueRecord,
        key_concern: str,
    ) -> str:
        deal_support = self._fetch_deal_support(record.lead_reference)
        if deal_support and deal_support.objection_response:
            body = deal_support.objection_response
            if key_concern:
                return (
                    f"Thanks for flagging the {key_concern.lower()} piece. "
                    f"{body}"
                )
            return body
        if key_concern:
            return (
                f"Thanks for the note on {key_concern.lower()}. Happy to show how we handle "
                f"that specifically — we can keep the next step light and walk through a "
                f"practical setup."
            )
        return (
            "Thanks for the note. Happy to walk through the practical setup so we can "
            "keep the next step light and address what matters most."
        )

    def _draft_request_for_info_response(
        self,
        record: OutreachQueueRecord,
        country: str,
    ) -> str:
        deal_support = self._fetch_deal_support(record.lead_reference)
        solution = self._fetch_solution(record.lead_reference)
        parts: list[str] = []
        if deal_support and deal_support.proposal_summary:
            parts.append(deal_support.proposal_summary)
        if solution and solution.commercial_strategy:
            parts.append(solution.commercial_strategy)
        if not parts:
            parts.append(
                f"Global Kinect runs payroll, HRIS, and EOR across {country} from one "
                "platform — one submission, one view of the workforce."
            )
        return " ".join(parts).strip()

    def _fetch_deal_support(self, lead_reference: str | None):
        if not lead_reference or not self.supabase_service.is_configured():
            return None
        try:
            return self.supabase_service.fetch_deal_support_package_by_lead_reference(
                lead_reference,
            )
        except Exception as exc:
            logger.warning("Deal support fetch failed for %s: %s", lead_reference, exc)
            return None

    def _fetch_solution(self, lead_reference: str | None):
        if not lead_reference or not self.supabase_service.is_configured():
            return None
        try:
            return self.supabase_service.fetch_solution_recommendation_by_lead_reference(
                lead_reference,
            )
        except Exception as exc:
            logger.warning("Solution fetch failed for %s: %s", lead_reference, exc)
            return None

    def _apply_updates(
        self,
        record: OutreachQueueRecord,
        reply_text: str,
        classification: dict[str, Any],
        drafted_message: str,
    ) -> None:
        label = classification["classification"]

        self._update_pipeline(record, label)
        self._update_queue_page(record, reply_text, classification, drafted_message)
        self._create_execution_task(record, label)

    def _update_pipeline(
        self,
        record: OutreachQueueRecord,
        label: str,
    ) -> None:
        if not record.lead_reference:
            return
        if not self.supabase_service.is_configured():
            return

        try:
            pipeline_record = self.supabase_service.fetch_pipeline_record_by_lead_reference(
                record.lead_reference,
            )
        except Exception as exc:
            logger.warning(
                "Pipeline lookup failed for %s: %s", record.lead_reference, exc
            )
            return
        if pipeline_record is None:
            return

        new_stage = CLASSIFICATION_TO_STAGE[label]
        updated = pipeline_record.model_copy(
            update={
                "outreach_status": "replied"
                if pipeline_record.outreach_status != "sent"
                else "replied",
                "stage": new_stage,
                "next_action": self._next_action_for(label),
                "last_response_at": utc_now_iso(),
                "last_updated_at": utc_now_iso(),
            }
        )
        try:
            self.supabase_service.update_pipeline_record(updated)
        except Exception as exc:
            logger.warning(
                "Pipeline persist failed for %s: %s", record.lead_reference, exc
            )
            return
        try:
            self.notion_service.upsert_pipeline_pages([updated])
        except Exception as exc:
            logger.warning(
                "Pipeline Notion sync failed for %s: %s", record.lead_reference, exc
            )

    def _next_action_for(self, label: str) -> str:
        if label == "negative":
            return "closed"
        if label == "out_of_office":
            return "wait"
        return "review_and_send_reply"

    def _update_queue_page(
        self,
        record: OutreachQueueRecord,
        reply_text: str,
        classification: dict[str, Any],
        drafted_message: str,
    ) -> None:
        label = classification["classification"]
        new_status = CLASSIFICATION_TO_QUEUE_STATUS[label]
        summary = classification.get("summary") or ""
        block_lines = [
            record.notes or "",
            "",
            "---RESPONSE HANDLER---",
            f"Classification: {label}",
        ]
        if summary:
            block_lines.append(f"Summary: {summary}")
        if classification.get("key_concern"):
            block_lines.append(f"Key concern: {classification['key_concern']}")
        block_lines.append(f"Reply received: {reply_text}")
        if drafted_message:
            block_lines.append("Drafted response:")
            block_lines.append(drafted_message)
        notes = "\n".join(line for line in block_lines if line is not None).strip()
        try:
            self.notion_service.update_outreach_queue_status_and_notes(
                page_id=record.page_id,
                status=new_status,
                notes=notes,
            )
        except Exception as exc:
            logger.warning(
                "Queue page update failed for %s: %s", record.page_id, exc
            )

    def _create_execution_task(
        self,
        record: OutreachQueueRecord,
        label: str,
    ) -> None:
        if not record.lead_reference:
            return

        description = (
            f"Review and send reply to {record.contact_name or 'the contact'} "
            f"at {record.company_name or 'the company'} — classified as {label}"
        )
        task = ExecutionTask(
            lead_reference=record.lead_reference,
            company_name=record.company_name,
            company_canonical=record.company_canonical,
            task_type="send_reply",
            description=description,
            priority=CLASSIFICATION_TO_TASK_PRIORITY[label],
            due_in_days=CLASSIFICATION_TO_DUE_IN_DAYS[label],
            status="open",
        )

        if self.supabase_service.is_configured():
            try:
                self.supabase_service.insert_execution_tasks([task])
            except Exception as exc:
                logger.warning(
                    "Task persist failed for %s: %s", record.lead_reference, exc
                )
        try:
            self.notion_service.upsert_execution_task_pages([task])
        except Exception as exc:
            logger.warning(
                "Task Notion sync failed for %s: %s", record.lead_reference, exc
            )

    def _build_response_event(
        self,
        record: OutreachQueueRecord,
        reply_text: str,
        classification: dict[str, Any],
        drafted_message: str,
    ) -> dict[str, Any]:
        label = classification["classification"]
        return {
            "lead_reference": record.lead_reference,
            "company_name": record.company_name,
            "contact_name": record.contact_name,
            "classification": label,
            "summary": classification.get("summary") or "",
            "key_concern": classification.get("key_concern"),
            "reply_text": reply_text,
            "drafted_response": drafted_message or None,
            "pipeline_stage_updated": CLASSIFICATION_TO_STAGE.get(label),
            "outreach_status_updated": CLASSIFICATION_TO_QUEUE_STATUS.get(label),
            "task_created": bool(record.lead_reference),
            "processed_at": utc_now_iso(),
        }

    def _print_shadow_output(
        self,
        record: OutreachQueueRecord,
        classification: dict[str, Any],
        drafted_message: str,
    ) -> None:
        print()
        print(f"[shadow] {record.lead_reference or record.page_id}")
        print(f"  Classification: {classification['classification']}")
        if classification.get("summary"):
            print(f"  Summary: {classification['summary']}")
        if classification.get("key_concern"):
            print(f"  Key concern: {classification['key_concern']}")
        if drafted_message:
            print(f"  Drafted: {drafted_message}")
        else:
            print("  Drafted: (no outbound message)")

    def _first_name(self, contact_name: str | None) -> str | None:
        if not contact_name:
            return None
        cleaned = contact_name.strip()
        if not cleaned:
            return None
        return cleaned.split()[0]
