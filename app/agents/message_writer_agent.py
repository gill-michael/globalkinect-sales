from typing import List

from app.models.lead import Lead
from app.models.outreach_message import OutreachMessage
from app.models.solution_recommendation import SolutionRecommendation
from app.utils.logger import get_logger
from app.utils.target_markets import country_label, country_subject_label

logger = get_logger(__name__)


class MessageWriterAgent:
    def generate_messages(self, leads: List[Lead]) -> List[OutreachMessage]:
        logger.warning(
            "generate_messages is a legacy path. Prefer generate_messages_with_solution."
        )
        logger.info(f"Generating legacy messages for {len(leads)} leads.")
        messages = [self._build_outreach_message(lead) for lead in leads]
        logger.info("Message generation completed.")
        return messages

    def generate_messages_with_solution(
        self,
        leads: List[Lead],
        solution_recommendations: List[SolutionRecommendation],
    ) -> List[OutreachMessage]:
        if len(leads) != len(solution_recommendations):
            raise ValueError("Lead and solution recommendation counts must match.")

        logger.info(f"Generating messages for {len(leads)} leads from solution recommendations.")
        messages = [
            self._build_outreach_message_with_solution(lead, solution_recommendation)
            for lead, solution_recommendation in zip(leads, solution_recommendations)
        ]
        logger.info("Solution-led message generation completed.")
        return messages

    def _build_outreach_message(self, lead: Lead) -> OutreachMessage:
        return OutreachMessage(
            lead_reference=self._build_lead_reference(lead),
            company_name=lead.company_name,
            contact_name=lead.contact_name,
            contact_role=lead.contact_role,
            lead_type=lead.lead_type or "unknown",
            target_country=lead.target_country or "unknown",
            sales_motion=None,
            primary_module=None,
            bundle_label=None,
            linkedin_message=self._build_linkedin_message(lead),
            email_subject=self._build_email_subject(lead),
            email_message=self._build_email_message(lead),
            follow_up_message=self._build_follow_up_message(lead),
        )

    def _build_outreach_message_with_solution(
        self,
        lead: Lead,
        solution_recommendation: SolutionRecommendation,
    ) -> OutreachMessage:
        return OutreachMessage(
            lead_reference=solution_recommendation.lead_reference,
            company_name=lead.company_name,
            contact_name=lead.contact_name,
            contact_role=lead.contact_role,
            lead_type=lead.lead_type or "unknown",
            target_country=lead.target_country or "unknown",
            sales_motion=solution_recommendation.sales_motion,
            primary_module=solution_recommendation.primary_module,
            bundle_label=solution_recommendation.bundle_label,
            linkedin_message=self._build_linkedin_message_with_solution(
                lead,
                solution_recommendation,
            ),
            email_subject=self._build_email_subject_with_solution(
                lead,
                solution_recommendation,
            ),
            email_message=self._build_email_message_with_solution(
                lead,
                solution_recommendation,
            ),
            follow_up_message=self._build_follow_up_message_with_solution(
                lead,
                solution_recommendation,
            ),
        )

    def _build_linkedin_message(self, lead: Lead) -> str:
        message = " ".join(
            [
                f"Hi {lead.contact_name},",
                self._role_hook(lead.contact_role),
                self._linkedin_value_line(lead),
                self._linkedin_close(lead.target_country),
            ]
        )
        return self._normalize_length(message, 300)

    def _build_email_subject(self, lead: Lead) -> str:
        country_label = self._country_subject_label(lead.target_country)
        subject_by_type = {
            "direct_eor": f"{country_label} hiring without entity setup",
            "direct_payroll": f"{country_label} payroll support",
            "recruitment_partner": f"{country_label} placement support",
            "hris": f"{country_label} HRIS and ops support",
        }
        return subject_by_type.get(
            lead.lead_type or "",
            f"{country_label} hiring support"
        )

    def _build_email_message(self, lead: Lead) -> str:
        sentences = [
            f"Hi {lead.contact_name},",
            self._email_context_line(lead),
            self._email_value_line(lead),
            self._recommended_angle_line(lead.recommended_angle),
            self._email_close(lead.target_country),
        ]
        return " ".join(sentence for sentence in sentences if sentence)

    def _build_follow_up_message(self, lead: Lead) -> str:
        follow_up_by_type = {
            "direct_eor": (
                f"Just following up in case {self._country_label(lead.target_country)} hiring is still active. "
                "We can help you hire without setting up a local entity first."
            ),
            "direct_payroll": (
                f"Just checking back on {self._country_label(lead.target_country)} payroll support. "
                "Happy to share a simple compliant setup if useful."
            ),
            "recruitment_partner": (
                f"Checking back in case you need an employment partner for {self._country_label(lead.target_country)} placements. "
                "We can support the employment and payroll side behind your hires."
            ),
            "hris": (
                f"Just following up in case tighter HR control in {self._country_label(lead.target_country)} is still on your list. "
                "We can support both local operations and HRIS visibility."
            ),
        }
        return follow_up_by_type.get(
            lead.lead_type or "",
            f"Just following up in case {self._country_label(lead.target_country)} hiring support is relevant."
        )

    def _build_linkedin_message_with_solution(
        self,
        lead: Lead,
        solution_recommendation: SolutionRecommendation,
    ) -> str:
        message = " ".join(
            [
                f"Hi {lead.contact_name},",
                self._role_hook(lead.contact_role),
                self._linkedin_value_line_with_solution(
                    lead,
                    solution_recommendation,
                ),
                self._linkedin_close_with_solution(
                    solution_recommendation,
                    lead.target_country,
                ),
            ]
        )
        return self._normalize_length(message, 300)

    def _build_email_subject_with_solution(
        self,
        lead: Lead,
        solution_recommendation: SolutionRecommendation,
    ) -> str:
        country_label = self._country_subject_label(lead.target_country)
        subject_by_bundle = {
            "EOR only": f"{country_label} EOR support",
            "Payroll only": f"{country_label} Payroll support",
            "HRIS only": f"{country_label} HRIS support",
            "EOR + Payroll": f"{country_label} EOR + Payroll support",
            "Payroll + HRIS": f"{country_label} Payroll + HRIS support",
            "EOR + HRIS": f"{country_label} EOR + HRIS support",
            "Full Platform": f"{country_label} Full Platform support",
        }
        return subject_by_bundle[solution_recommendation.bundle_label]

    def _build_email_message_with_solution(
        self,
        lead: Lead,
        solution_recommendation: SolutionRecommendation,
    ) -> str:
        sentences = [
            f"Hi {lead.contact_name},",
            self._email_context_line_with_solution(lead, solution_recommendation),
            self._email_value_line_with_solution(lead, solution_recommendation),
            self._strategy_line(solution_recommendation.commercial_strategy),
            self._email_close_with_solution(solution_recommendation, lead.target_country),
        ]
        return " ".join(sentence for sentence in sentences if sentence)

    def _build_follow_up_message_with_solution(
        self,
        lead: Lead,
        solution_recommendation: SolutionRecommendation,
    ) -> str:
        country_label = self._country_label(lead.target_country)
        bundle_label = self._bundle_display_label(
            solution_recommendation,
            include_modules=solution_recommendation.bundle_label == "Full Platform",
        )

        if solution_recommendation.sales_motion == "recruitment_partner":
            return (
                f"Checking back in case the {bundle_label} partner model for "
                f"{country_label} placements is still relevant. Happy to share a practical outline if useful."
            )

        follow_up_by_bundle = {
            "EOR only": (
                f"Just following up in case EOR support for {country_label} is still relevant. "
                "Happy to share a concise outline if useful."
            ),
            "Payroll only": (
                f"Just checking back in case payroll support for {country_label} is still relevant. "
                "Happy to share a practical setup if useful."
            ),
            "HRIS only": (
                f"Just following up in case stronger HR control for {country_label} is still on your list. "
                "Happy to share a concise outline if useful."
            ),
            "EOR + Payroll": (
                f"Checking back in case an EOR + Payroll setup for {country_label} is still relevant. "
                "We can cover both market entry and payroll execution together."
            ),
            "Payroll + HRIS": (
                f"Checking back in case a {bundle_label} setup for {country_label} is still relevant. "
                "We can support payroll delivery and stronger operating control in one model."
            ),
            "EOR + HRIS": (
                f"Checking back in case an {bundle_label} setup for {country_label} is still relevant. "
                "Happy to share how that would work in practice."
            ),
            "Full Platform": (
                f"Checking back in case a {bundle_label} setup for {country_label} is still relevant. "
                "Happy to share how the model would work in practice."
            ),
        }
        return follow_up_by_bundle[solution_recommendation.bundle_label]

    def _build_lead_reference(self, lead: Lead) -> str:
        parts = [
            lead.company_name,
            lead.contact_name,
            self._country_label(lead.target_country),
            lead.lead_type or "unknown",
        ]
        return "|".join(parts)

    def _role_hook(self, contact_role: str) -> str:
        normalized_role = contact_role.lower()

        if "founder" in normalized_role:
            return "Reaching out because you are likely balancing speed with market-entry risk."
        if "people" in normalized_role or "hr" in normalized_role:
            return "Reaching out because hiring quality and compliance usually sit with your team."
        if "director" in normalized_role:
            return "Reaching out because execution quality and internal bandwidth usually matter at your level."
        return "Reaching out in case hiring support is relevant on your side."

    def _linkedin_value_line(self, lead: Lead) -> str:
        return {
            "direct_eor": f"We help companies hire into {self._country_label(lead.target_country)} without setting up an entity, with local payroll and compliance covered.",
            "direct_payroll": f"We help teams run compliant payroll in {self._country_label(lead.target_country)} without building a heavy local setup.",
            "recruitment_partner": f"We support recruiters placing talent into {self._country_label(lead.target_country)} by handling compliant employment and payroll.",
            "hris": f"We help teams tighten HR operations in {self._country_label(lead.target_country)} with stronger control and visibility.",
        }.get(
            lead.lead_type or "",
            f"We support practical hiring, payroll, and people operations in {self._country_label(lead.target_country)}."
        )

    def _linkedin_value_line_with_solution(
        self,
        lead: Lead,
        solution_recommendation: SolutionRecommendation,
    ) -> str:
        country_label = self._country_label(lead.target_country)

        if solution_recommendation.sales_motion == "recruitment_partner":
            return (
                f"We support placements into {country_label} through an {solution_recommendation.bundle_label} "
                "model that handles employment and payroll behind the scenes."
            )

        value_lines = {
            "EOR only": (
                f"We help teams hire into {country_label} through a compliant EOR model."
            ),
            "Payroll only": (
                f"We help teams run compliant payroll in {country_label} without building a heavy local setup."
            ),
            "HRIS only": (
                f"We help teams add stronger HR visibility and control in {country_label}."
            ),
            "EOR + Payroll": (
                f"We help teams hire into {country_label} without an entity while covering payroll execution from day one."
            ),
            "Payroll + HRIS": (
                f"We help teams put compliant payroll in place in {country_label} and add stronger operating control."
            ),
            "EOR + HRIS": (
                f"We help teams enter {country_label} with compliant employment and clearer HR control."
            ),
            "Full Platform": (
                f"We help teams run hiring, payroll, and HR control in {country_label} through one operating platform."
            ),
        }
        return value_lines[solution_recommendation.bundle_label]

    def _email_context_line(self, lead: Lead) -> str:
        return {
            "direct_eor": (
                f"Teams expanding into {self._country_label(lead.target_country)} often want to hire quickly without waiting on entity setup."
            ),
            "direct_payroll": (
                f"Payroll into {self._country_label(lead.target_country)} usually becomes painful before a team wants to build local infrastructure."
            ),
            "recruitment_partner": (
                f"Recruiters placing candidates into {self._country_label(lead.target_country)} often need a reliable partner behind the employment and payroll piece."
            ),
            "hris": (
                f"Distributed hiring into {self._country_label(lead.target_country)} often exposes gaps in process visibility and operating control."
            ),
        }.get(
            lead.lead_type or "",
            f"Hiring into {self._country_label(lead.target_country)} often needs both compliance support and practical execution."
        )

    def _email_context_line_with_solution(
        self,
        lead: Lead,
        solution_recommendation: SolutionRecommendation,
    ) -> str:
        country_label = self._country_label(lead.target_country)

        if solution_recommendation.sales_motion == "recruitment_partner":
            return (
                f"From what I can see, placements into {country_label} usually need a dependable "
                "employment and payroll model behind delivery."
            )

        context_by_bundle = {
            "EOR only": (
                f"From what I can see, the fit is a compliant EOR setup in {country_label} without unnecessary local overhead."
            ),
            "Payroll only": (
                f"From what I can see, the fit is focused payroll support in {country_label} without building local infrastructure too early."
            ),
            "HRIS only": (
                f"From what I can see, the fit is tighter HR visibility and process control in {country_label}."
            ),
            "EOR + Payroll": (
                f"From what I can see, the fit is an EOR + Payroll model in {country_label} so hiring can move without waiting on entity setup."
            ),
            "Payroll + HRIS": (
                f"From what I can see, the fit is a payroll-led model in {country_label} with better day-to-day visibility and control."
            ),
            "EOR + HRIS": (
                f"From what I can see, the fit is a hiring model in {country_label} that also gives the team clearer HR structure and visibility."
            ),
            "Full Platform": (
                f"From what I can see, the fit is a single operating platform in {country_label} rather than separate workstreams for hiring, payroll, and HR."
            ),
        }
        return context_by_bundle[solution_recommendation.bundle_label]

    def _email_value_line(self, lead: Lead) -> str:
        return {
            "direct_eor": "We act as the local employer so your team can hire compliantly and move faster in market.",
            "direct_payroll": "We run compliant local payroll with regional GCC execution support.",
            "recruitment_partner": "We support your placements by taking on compliant employment, payroll, and local execution.",
            "hris": "We support the operating layer while improving HR structure and visibility across the employee lifecycle.",
        }.get(
            lead.lead_type or "",
            "We support practical EOR, payroll, and people operations for cross-border teams."
        )

    def _email_value_line_with_solution(
        self,
        lead: Lead,
        solution_recommendation: SolutionRecommendation,
    ) -> str:
        country_label = self._country_label(lead.target_country)
        bundle_label = self._bundle_display_label(
            solution_recommendation,
            include_modules=solution_recommendation.bundle_label == "Full Platform",
        )
        return (
            f"The commercial entry point is {solution_recommendation.primary_module}, with "
            f"{bundle_label} covering the wider need in {country_label}."
        )

    def _recommended_angle_line(self, recommended_angle: str | None) -> str:
        if not recommended_angle:
            return ""
        if "entity" in recommended_angle.lower():
            return "This tends to work well when the priority is hiring before a local entity is in place."
        if "partner" in recommended_angle.lower() or "placements" in recommended_angle.lower():
            return "It is especially relevant when placements need a dependable local employment and payroll partner."
        if "payroll" in recommended_angle.lower():
            return "It is usually most useful when compliant payroll needs to be in place from day one."
        if "hris" in recommended_angle.lower() or "visibility" in recommended_angle.lower():
            return "It is usually most relevant when the team wants tighter operational control as hiring expands."
        return "The model is designed to stay practical and execution-focused."

    def _linkedin_close(self, target_country: str | None) -> str:
        return f"Happy to share how companies usually handle this in {self._country_label(target_country)} if useful."

    def _email_close(self, target_country: str | None) -> str:
        return f"If useful, I can send a simple outline of how teams typically handle this in {self._country_label(target_country)}."

    def _linkedin_close_with_solution(
        self,
        solution_recommendation: SolutionRecommendation,
        target_country: str | None,
    ) -> str:
        bundle_label = self._bundle_display_label(
            solution_recommendation,
            include_modules=solution_recommendation.bundle_label == "Full Platform",
        )
        return (
            f"Happy to share how a {bundle_label} setup usually works in "
            f"{self._country_label(target_country)} if useful."
        )

    def _email_close_with_solution(
        self,
        solution_recommendation: SolutionRecommendation,
        target_country: str | None,
    ) -> str:
        bundle_label = self._bundle_display_label(
            solution_recommendation,
            include_modules=solution_recommendation.bundle_label == "Full Platform",
        )
        return (
            f"If useful, I can send a concise outline of the {bundle_label} "
            f"model for {self._country_label(target_country)}."
        )

    def _bundle_display_label(
        self,
        solution_recommendation: SolutionRecommendation,
        include_modules: bool = False,
    ) -> str:
        if include_modules and solution_recommendation.bundle_label == "Full Platform":
            modules_label = ", ".join(solution_recommendation.recommended_modules)
            return f"Full Platform ({modules_label})"
        return solution_recommendation.bundle_label

    def _strategy_line(self, commercial_strategy: str) -> str:
        normalized = commercial_strategy.rstrip(".")
        lowered = normalized.lower()

        if lowered.startswith("position "):
            remainder = normalized[9:]
            if remainder.startswith("GlobalKinect"):
                return f"The practical fit here is {remainder}."
            return f"The practical fit here is {remainder[0].lower() + remainder[1:]}."

        if lowered.startswith("lead with "):
            remainder = normalized[10:]
            return f"A strong fit here is {remainder}."

        return normalized + "."

    def _country_label(self, target_country: str | None) -> str:
        return country_label(target_country)

    def _country_subject_label(self, target_country: str | None) -> str:
        return country_subject_label(target_country)

    def _normalize_length(self, message: str, max_length: int) -> str:
        normalized = " ".join(message.split())
        if len(normalized) <= max_length:
            return normalized
        return normalized[: max_length - 3].rstrip() + "..."
