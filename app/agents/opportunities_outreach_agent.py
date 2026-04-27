import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.models.opportunity_record import OpportunityRecord
from app.models.outreach_message import OutreachMessage
from app.models.outreach_queue_item import OutreachQueueItem
from app.services.anthropic_service import AnthropicService
from app.services.config import settings
from app.services.notion_service import NotionService
from app.services.supabase_service import SupabaseService
from app.utils.logger import get_logger
from app.utils.time import utc_now, utc_now_iso

logger = get_logger(__name__)


ICP_HOOK_FILES: dict[str, str] = {
    "A1 - Frustrated GCC Operator": "outreach/icp-hooks/A1-frustrated-gcc-operator.md",
    "A2 - GCC SME": "outreach/icp-hooks/A2-gcc-sme.md",
    "A3 - Scaling GCC Business": "outreach/icp-hooks/A3-scaling-gcc-business.md",
    "B1 - European Multi-Country": "outreach/icp-hooks/B1-european-multicountry.md",
    "B2 - UK Domestic SME": "outreach/icp-hooks/B2-uk-domestic-sme.md",
    "B3 - International MENA Expander": "outreach/icp-hooks/B3-international-mena-expander.md",
    "B4 - European-MENA Bridge": "outreach/icp-hooks/B4-european-mena-bridge.md",
    "B5 - HRIS Platform Partner": "outreach/partner-hooks/B5-hris-platform-partner.md",
}

MENA_FOCUSED_ICPS = {
    "A1 - Frustrated GCC Operator",
    "A2 - GCC SME",
    "A3 - Scaling GCC Business",
    "B3 - International MENA Expander",
}
EUROPEAN_FOCUSED_ICPS = {
    "B1 - European Multi-Country",
    "B2 - UK Domestic SME",
    "B4 - European-MENA Bridge",
}

BATCH_SIZE = 10
API_CALL_DELAY_SECONDS = 2.0
OUTREACH_GENERATED_MARKER = "---OUTREACH GENERATED---"

BANNED_PHRASES = [
    "partner network",
    "local bureau",
    "third-party provider",
    "third party provider",
    "powered by",
    "in partnership with",
    "i hope this message finds you well",
    "i hope this finds you well",
    "i hope this email finds you well",
    "i hope you are well",
    "i hope this finds you well.",
]
BANNED_PRODUCT_NAMES = ["Insight", "Orchestrate", "Control"]

SYSTEM_PROMPT_MENA = (
    "You are a B2B outreach specialist for Global Kinect — a Payroll Bureau, "
    "HRIS, and EOR platform covering 11 MENA countries (Saudi Arabia, UAE, Qatar, "
    "Kuwait, Bahrain, Oman, Egypt, Morocco, Algeria, Lebanon, Jordan). "
    "You write direct, specific, human outreach messages. You never use generic "
    "openers. You never mention our partner network, third-party providers, or "
    "local bureaus. You never use the product names Insight, Orchestrate, or "
    "Control. You always write Global Kinect as two words. You follow the voice "
    "and hook patterns provided exactly."
)

SYSTEM_PROMPT_EUROPEAN = (
    "You are a B2B outreach specialist for Global Kinect — a Payroll Bureau, "
    "HRIS, and EOR platform covering 100+ countries. "
    "You write direct, specific, human outreach messages. You never use generic "
    "openers. You never mention our partner network, third-party providers, or "
    "local bureaus. You never use the product names Insight, Orchestrate, or "
    "Control. You always write Global Kinect as two words. You follow the voice "
    "and hook patterns provided exactly."
)

SYSTEM_PROMPT_DEFAULT = (
    "You are a B2B outreach specialist for Global Kinect — a Payroll Bureau, "
    "HRIS, and EOR platform. You write direct, specific, human outreach messages. "
    "You never use generic openers. You never mention our partner network, "
    "third-party providers, or local bureaus. You never use the product names "
    "Insight, Orchestrate, or Control. You always write Global Kinect as two "
    "words. You follow the voice and hook patterns provided exactly."
)


@dataclass
class OutreachGenerationResult:
    processed_count: int = 0
    generated_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0
    failures: list[tuple[str, str]] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"processed={self.processed_count} generated={self.generated_count} "
            f"failed={self.failed_count} skipped={self.skipped_count}"
        )


class OpportunitiesOutreachAgent:
    def __init__(
        self,
        notion_service: NotionService,
        anthropic_service: AnthropicService,
        supabase_service: SupabaseService,
        branding_repo_path: str | None = None,
        sleep_fn=time.sleep,
    ) -> None:
        self.notion_service = notion_service
        self.anthropic_service = anthropic_service
        self.supabase_service = supabase_service
        self.branding_repo_path = Path(
            branding_repo_path or settings.BRANDING_REPO_PATH
        )
        self._sleep = sleep_fn
        self._hook_library = self._load_hook_library()

    def is_configured(self) -> bool:
        return (
            self.notion_service.is_opportunities_configured()
            and self.notion_service.is_outreach_queue_configured()
            and self.anthropic_service.is_configured()
        )

    def generate_outreach(
        self,
        limit: int = 50,
        icp_filter: str | None = None,
    ) -> OutreachGenerationResult:
        if not self.is_configured():
            raise RuntimeError(
                "OpportunitiesOutreachAgent is not fully configured. "
                "Check NOTION_OPPORTUNITIES_DATABASE_ID, "
                "NOTION_OUTREACH_QUEUE_DATABASE_ID, and ANTHROPIC_API_KEY."
            )

        logger.info(
            "Fetching eligible opportunities (limit=%s, icp_filter=%s).",
            limit,
            icp_filter or "none",
        )
        prospects = self.notion_service.fetch_opportunity_pages(
            limit=limit,
            icp_filter=icp_filter,
        )

        result = OutreachGenerationResult()
        run_marker = f"OPPS_{utc_now().strftime('%Y%m%d%H%M%S')}"

        for batch_index, batch in enumerate(self._chunked(prospects, BATCH_SIZE), start=1):
            for prospect in batch:
                self._process_prospect(prospect, run_marker, result)
                if API_CALL_DELAY_SECONDS > 0:
                    self._sleep(API_CALL_DELAY_SECONDS)
            logger.info(
                "Batch %s complete. Running totals: %s", batch_index, result.summary()
            )

        logger.info("Outreach generation finished. %s", result.summary())
        return result

    def _process_prospect(
        self,
        prospect: OpportunityRecord,
        run_marker: str,
        result: OutreachGenerationResult,
    ) -> None:
        result.processed_count += 1
        prospect_label = f"{prospect.company_name} ({prospect.page_id})"

        if not prospect.icp or prospect.icp.strip().lower() in {"unknown", ""}:
            logger.warning("Skipping %s — ICP is unknown.", prospect_label)
            result.skipped_count += 1
            self._mark_prospect_failed(prospect, "ICP is unknown")
            return

        hook_content = self._hook_library.get(prospect.icp)
        if hook_content is None:
            logger.warning(
                "Skipping %s — no hook library for ICP %s.",
                prospect_label,
                prospect.icp,
            )
            result.skipped_count += 1
            self._mark_prospect_failed(
                prospect, f"No hook library for ICP {prospect.icp}"
            )
            return

        try:
            generated = self._call_anthropic(prospect, hook_content)
        except Exception as exc:
            logger.warning("Anthropic call failed for %s: %s", prospect_label, exc)
            result.failed_count += 1
            result.failures.append((prospect_label, f"anthropic_error: {exc}"))
            self._mark_prospect_failed(prospect, f"Anthropic error: {exc}")
            return

        if generated is None:
            logger.warning("No structured response from Anthropic for %s.", prospect_label)
            result.failed_count += 1
            result.failures.append((prospect_label, "anthropic_empty_response"))
            self._mark_prospect_failed(prospect, "Anthropic returned no content")
            return

        linkedin_message = generated.get("linkedin_message", "").strip()
        email_subject = generated.get("email_subject", "").strip()
        email_body = generated.get("email_body", "").strip()

        is_valid, reason = self._validate(
            linkedin_message, email_subject, email_body, prospect.icp
        )
        if not is_valid:
            logger.warning(
                "Generated content for %s violates brand rules: %s",
                prospect_label,
                reason,
            )
            result.failed_count += 1
            result.failures.append((prospect_label, f"validation: {reason}"))
            self._mark_prospect_failed(prospect, f"Brand rule violation: {reason}")
            return

        try:
            self._persist(prospect, linkedin_message, email_subject, email_body, run_marker)
            self._mark_prospect_generated(
                prospect, linkedin_message, email_subject, email_body
            )
        except Exception as exc:
            logger.warning("Persistence failed for %s: %s", prospect_label, exc)
            result.failed_count += 1
            result.failures.append((prospect_label, f"persistence_error: {exc}"))
            return

        result.generated_count += 1

    def _load_hook_library(self) -> dict[str, str]:
        library: dict[str, str] = {}
        for icp_label, relative_path in ICP_HOOK_FILES.items():
            full_path = self.branding_repo_path / relative_path
            try:
                library[icp_label] = full_path.read_text(encoding="utf-8")
            except FileNotFoundError:
                logger.warning(
                    "Hook file missing for ICP %s at %s.", icp_label, full_path
                )
                continue
            except OSError as exc:
                logger.warning(
                    "Could not read hook file for ICP %s at %s: %s",
                    icp_label,
                    full_path,
                    exc,
                )
                continue
        logger.info("Loaded %s ICP hook files from %s.", len(library), self.branding_repo_path)
        return library

    def _call_anthropic(
        self,
        prospect: OpportunityRecord,
        hook_content: str,
    ) -> dict[str, Any] | None:
        user_prompt = self._build_user_prompt(prospect, hook_content)
        system_prompt = self._build_system_prompt(prospect.icp)
        response = self.anthropic_service.client.messages.create(
            model=self.anthropic_service.model,
            max_tokens=1500,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        text_blocks = [
            block.text
            for block in response.content
            if getattr(block, "type", None) == "text"
        ]
        if not text_blocks:
            return None
        raw_text = "\n".join(text_blocks).strip()
        return self._parse_json_response(raw_text)

    def _build_system_prompt(self, icp: str) -> str:
        if icp in MENA_FOCUSED_ICPS:
            return SYSTEM_PROMPT_MENA
        if icp in EUROPEAN_FOCUSED_ICPS:
            return SYSTEM_PROMPT_EUROPEAN
        return SYSTEM_PROMPT_DEFAULT

    def _parse_json_response(self, raw_text: str) -> dict[str, Any] | None:
        if not raw_text:
            return None
        candidate = raw_text.strip()
        if candidate.startswith("```"):
            candidate = candidate.strip("`")
            if candidate.lower().startswith("json"):
                candidate = candidate[4:]
            candidate = candidate.strip()
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        try:
            parsed = json.loads(candidate[start : end + 1])
        except json.JSONDecodeError:
            return None
        if not isinstance(parsed, dict):
            return None
        return parsed

    def _build_user_prompt(
        self,
        prospect: OpportunityRecord,
        hook_content: str,
    ) -> str:
        countries_text = ", ".join(prospect.countries) if prospect.countries else "unspecified"
        notes_text = prospect.notes or "none"
        return (
            "Generate two outreach messages for this prospect.\n\n"
            "Prospect details:\n"
            f"Name: {prospect.contact_name or 'unknown'}\n"
            f"Role: {prospect.contact_role or 'unknown'}\n"
            f"Company: {prospect.company_name}\n"
            f"Country: {countries_text}\n"
            f"Notes: {notes_text}\n"
            f"ICP: {prospect.icp}\n\n"
            "Hook library for this ICP:\n"
            f"{hook_content}\n\n"
            "Rules:\n"
            "- LinkedIn message: maximum 5 lines, no bullet points, one specific "
            "observation about their company or role, one sentence on what "
            "Global Kinect covers, one ask for a 20-minute call. Never use "
            "'I hope this finds you well' or any equivalent opener.\n"
            "- Email subject line: under 8 words, specific to their situation, "
            "not generic.\n"
            "- Email body: maximum 6 lines, same structure as LinkedIn but "
            "slightly more detail permitted.\n"
            "- Use their name in the opening line.\n"
            "- Reference their country or city where relevant.\n"
            "- Reference their industry or role where visible in Notes.\n"
            "- If no specific company signal is visible, use the ICP-level hook "
            "pattern from the hook library.\n"
            "- Never mention competitor names.\n"
            "- Never mention that Global Kinect uses local partners.\n"
            "- Always write 'Global Kinect' as two words.\n"
            f"- Coverage claim: use '11 MENA countries' for MENA-focused prospects "
            f"({', '.join(sorted(MENA_FOCUSED_ICPS))}); use '100+ countries' for "
            f"European prospects ({', '.join(sorted(EUROPEAN_FOCUSED_ICPS))}). "
            "Never '30+ countries'.\n"
            "- Output format: return JSON only with these keys: "
            "linkedin_message, email_subject, email_body."
        )

    def _validate(
        self,
        linkedin_message: str,
        email_subject: str,
        email_body: str,
        icp: str,
    ) -> tuple[bool, str]:
        if not linkedin_message:
            return False, "linkedin_message missing"
        if not email_subject:
            return False, "email_subject missing"
        if not email_body:
            return False, "email_body missing"

        combined_lower = " ".join([linkedin_message, email_subject, email_body]).lower()

        if "globalkinect" in combined_lower:
            # Diagnostic message intentionally retains the one-word form so
            # operators can see exactly what shape was rejected. The string is
            # error metadata, not customer-facing copy.
            return False, "contains one-word 'GlobalKinect'"

        for phrase in BANNED_PHRASES:
            if phrase in combined_lower:
                return False, f"contains banned phrase: {phrase}"

        for product in BANNED_PRODUCT_NAMES:
            if self._word_in_text(product, linkedin_message) or self._word_in_text(
                product, email_body
            ):
                return False, f"contains product name: {product}"

        if "30+ countries" in combined_lower:
            return False, "contains banned '30+ countries' claim"

        if icp in MENA_FOCUSED_ICPS and "100+ countries" in combined_lower:
            return False, "MENA-focused ICP must not use '100+ countries' claim"
        if icp in EUROPEAN_FOCUSED_ICPS and "11 mena countries" in combined_lower:
            return False, "European-focused ICP must not use '11 MENA countries' claim"

        linkedin_lines = self._count_non_empty_lines(linkedin_message)
        if linkedin_lines > 5:
            return False, f"LinkedIn message has {linkedin_lines} lines (max 5)"
        email_lines = self._count_non_empty_lines(email_body)
        if email_lines > 6:
            return False, f"Email body has {email_lines} lines (max 6)"

        if self._has_bullet_points(linkedin_message) or self._has_bullet_points(email_body):
            return False, "contains bullet points"

        return True, ""

    def _count_non_empty_lines(self, text: str) -> int:
        return sum(1 for line in text.splitlines() if line.strip())

    def _has_bullet_points(self, text: str) -> bool:
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if stripped[0] in {"-", "*", "•"} and (len(stripped) == 1 or stripped[1] == " "):
                return True
        return False

    def _word_in_text(self, word: str, text: str) -> bool:
        import re

        pattern = r"\b" + re.escape(word) + r"\b"
        return re.search(pattern, text) is not None

    def _persist(
        self,
        prospect: OpportunityRecord,
        linkedin_message: str,
        email_subject: str,
        email_body: str,
        run_marker: str,
    ) -> None:
        lead_reference = self._build_lead_reference(prospect)
        target_country = self._primary_country(prospect)
        contact_name = prospect.contact_name or "Unknown Contact"
        contact_role = prospect.contact_role or "Unknown Role"

        outreach_message = OutreachMessage(
            lead_reference=lead_reference,
            company_name=prospect.company_name,
            contact_name=contact_name,
            contact_role=contact_role,
            lead_type="opportunity",
            target_country=target_country,
            sales_motion=None,
            primary_module=None,
            bundle_label=None,
            linkedin_message=linkedin_message,
            email_subject=email_subject,
            email_message=email_body,
            follow_up_message="",
        )

        if self.supabase_service.is_configured():
            self.supabase_service.insert_outreach_messages([outreach_message])

        queue_item = OutreachQueueItem(
            lead_reference=lead_reference,
            company_name=prospect.company_name,
            contact_name=contact_name,
            contact_role=contact_role,
            priority=self._priority_from_fit_score(prospect.fit_score),
            target_country=target_country,
            sales_motion=None,
            primary_module=None,
            bundle_label=None,
            email_subject=email_subject,
            email_message=email_body,
            linkedin_message=linkedin_message,
            follow_up_message="",
            status="ready_to_send",
            generated_at=utc_now_iso(),
            run_marker=run_marker,
            notes=f"Sourced from Opportunities database (ICP {prospect.icp}).",
        )
        self.notion_service.upsert_outreach_queue_pages([queue_item])

    def _mark_prospect_generated(
        self,
        prospect: OpportunityRecord,
        linkedin_message: str,
        email_subject: str,
        email_body: str,
    ) -> None:
        appended = self._append_outreach_block(
            prospect.notes, linkedin_message, email_subject, email_body
        )
        today_iso = utc_now().date().isoformat()
        properties = {
            "Next Action": self.notion_service._rich_text("Review outreach in dashboard"),
            "Next Action Date": self.notion_service._date(today_iso),
            "Notes": self.notion_service._rich_text(appended),
        }
        self.notion_service.update_opportunity_page(prospect.page_id, properties)

    def _mark_prospect_failed(
        self,
        prospect: OpportunityRecord,
        reason: str,
    ) -> None:
        try:
            properties = {
                "Next Action": self.notion_service._rich_text(
                    f"Outreach generation failed — {reason}"
                ),
                "Next Action Date": self.notion_service._date(
                    utc_now().date().isoformat()
                ),
            }
            self.notion_service.update_opportunity_page(prospect.page_id, properties)
        except Exception as exc:
            logger.warning(
                "Could not mark prospect %s as failed: %s", prospect.page_id, exc
            )

    def _append_outreach_block(
        self,
        existing_notes: str | None,
        linkedin_message: str,
        email_subject: str,
        email_body: str,
    ) -> str:
        block = (
            f"\n\n{OUTREACH_GENERATED_MARKER}\n"
            f"LinkedIn:\n{linkedin_message}\n\n"
            f"Email subject: {email_subject}\n\n"
            f"Email:\n{email_body}"
        )
        base = existing_notes or ""
        if OUTREACH_GENERATED_MARKER in base:
            base = base.split(OUTREACH_GENERATED_MARKER, 1)[0].rstrip()
        return (base + block).strip()

    def _build_lead_reference(self, prospect: OpportunityRecord) -> str:
        parts = [
            "OPP",
            prospect.page_id.replace("-", "")[:12],
            prospect.company_name,
            prospect.contact_name or "Unknown Contact",
        ]
        return "|".join(parts)

    def _primary_country(self, prospect: OpportunityRecord) -> str:
        if prospect.countries:
            return prospect.countries[0]
        return "unspecified"

    def _priority_from_fit_score(self, fit_score: int | None) -> str:
        if fit_score is None:
            return "medium"
        if fit_score >= 8:
            return "high"
        if fit_score >= 5:
            return "medium"
        return "low"

    def _chunked(self, items: list[Any], size: int):
        for start in range(0, len(items), size):
            yield items[start : start + size]
