from typing import List

from app.models.deal_support_package import DealSupportPackage
from app.models.lead import Lead
from app.models.pipeline_record import PipelineRecord
from app.models.solution_recommendation import SolutionRecommendation
from app.utils.logger import get_logger
from app.utils.target_markets import country_label, country_subject_label

logger = get_logger(__name__)


class ProposalSupportAgent:
    def create_deal_support_package(
        self,
        lead: Lead,
        pipeline_record: PipelineRecord,
    ) -> DealSupportPackage:
        logger.warning(
            "create_deal_support_package is a legacy path. Prefer "
            "create_deal_support_package_with_solution."
        )
        logger.info(f"Creating deal support package for {pipeline_record.lead_reference}.")
        return DealSupportPackage(
            lead_reference=pipeline_record.lead_reference,
            company_name=lead.company_name,
            contact_name=lead.contact_name,
            lead_type=lead.lead_type or "unknown",
            target_country=lead.target_country or "unknown",
            sales_motion=None,
            primary_module=None,
            bundle_label=None,
            recommended_modules=None,
            stage=pipeline_record.stage,
            call_prep_summary=self._build_call_prep_summary(lead, pipeline_record),
            recap_email_subject=self._build_recap_email_subject(lead, pipeline_record),
            recap_email_body=self._build_recap_email_body(lead, pipeline_record),
            proposal_summary=self._build_proposal_summary(lead, pipeline_record),
            next_steps_message=self._build_next_steps_message(lead, pipeline_record),
            objection_response=self._build_objection_response(lead, pipeline_record),
        )

    def create_deal_support_packages(
        self,
        leads: List[Lead],
        pipeline_records: List[PipelineRecord],
    ) -> List[DealSupportPackage]:
        logger.warning(
            "create_deal_support_packages is a legacy path. Prefer "
            "create_deal_support_packages_with_solution."
        )
        if len(leads) != len(pipeline_records):
            raise ValueError("Lead and pipeline record counts must match.")

        logger.info(f"Creating {len(leads)} deal support packages.")
        packages = [
            self.create_deal_support_package(lead, record)
            for lead, record in zip(leads, pipeline_records)
        ]
        logger.info("Deal support package creation completed.")
        return packages

    def create_deal_support_package_with_solution(
        self,
        lead: Lead,
        pipeline_record: PipelineRecord,
        solution_recommendation: SolutionRecommendation,
    ) -> DealSupportPackage:
        logger.info(
            f"Creating solution-led deal support package for {pipeline_record.lead_reference}."
        )
        return DealSupportPackage(
            lead_reference=solution_recommendation.lead_reference,
            company_name=lead.company_name,
            contact_name=lead.contact_name,
            lead_type=lead.lead_type or "unknown",
            target_country=lead.target_country or "unknown",
            sales_motion=solution_recommendation.sales_motion,
            primary_module=solution_recommendation.primary_module,
            bundle_label=solution_recommendation.bundle_label,
            recommended_modules=solution_recommendation.recommended_modules,
            stage=pipeline_record.stage,
            call_prep_summary=self._build_call_prep_summary_with_solution(
                lead,
                pipeline_record,
                solution_recommendation,
            ),
            recap_email_subject=self._build_recap_email_subject_with_solution(
                lead,
                solution_recommendation,
            ),
            recap_email_body=self._build_recap_email_body_with_solution(
                lead,
                pipeline_record,
                solution_recommendation,
            ),
            proposal_summary=self._build_proposal_summary_with_solution(
                lead,
                solution_recommendation,
            ),
            next_steps_message=self._build_next_steps_message_with_solution(
                lead,
                solution_recommendation,
            ),
            objection_response=self._build_objection_response_with_solution(
                lead,
                solution_recommendation,
            ),
        )

    def create_deal_support_packages_with_solution(
        self,
        leads: List[Lead],
        pipeline_records: List[PipelineRecord],
        solution_recommendations: List[SolutionRecommendation],
    ) -> List[DealSupportPackage]:
        if (
            len(leads) != len(pipeline_records)
            or len(leads) != len(solution_recommendations)
        ):
            raise ValueError(
                "Lead, pipeline record, and solution recommendation counts must match."
            )

        logger.info(f"Creating {len(leads)} solution-led deal support packages.")
        packages = [
            self.create_deal_support_package_with_solution(
                lead,
                pipeline_record,
                solution_recommendation,
            )
            for lead, pipeline_record, solution_recommendation in zip(
                leads,
                pipeline_records,
                solution_recommendations,
            )
        ]
        logger.info("Solution-led deal support package creation completed.")
        return packages

    def _build_call_prep_summary(
        self,
        lead: Lead,
        pipeline_record: PipelineRecord,
    ) -> str:
        priority_line = {
            "high": "This is a high-priority opportunity worth driving toward a defined next step on the call.",
            "medium": "Focus on confirming urgency, decision ownership, and practical buying criteria.",
            "low": "Use the call to confirm whether there is a real near-term project before investing more time.",
        }.get(pipeline_record.priority, "Use the call to qualify urgency and commercial fit.")

        angle_line = lead.recommended_angle or "Lead with practical execution support."
        motion_line = {
            "direct_eor": (
                f"Likely motion: hiring into {self._country_label(lead.target_country)} without waiting for entity setup."
            ),
            "direct_payroll": (
                f"Likely motion: compliant payroll delivery for employees in {self._country_label(lead.target_country)}."
            ),
            "recruitment_partner": (
                f"Likely motion: supporting placements into {self._country_label(lead.target_country)} with employment and payroll infrastructure."
            ),
            "hris": (
                f"Likely motion: improving HR control and process visibility for the team in {self._country_label(lead.target_country)}."
            ),
        }.get(
            lead.lead_type or "",
            f"Likely motion: supporting market entry and operations in {self._country_label(lead.target_country)}."
        )
        return " ".join([priority_line, motion_line, f"Commercial angle: {angle_line}"])

    def _build_recap_email_subject(
        self,
        lead: Lead,
        pipeline_record: PipelineRecord,
    ) -> str:
        subject_by_type = {
            "direct_eor": f"Recap: {self._country_subject_label(lead.target_country)} hiring support",
            "direct_payroll": f"Recap: {self._country_subject_label(lead.target_country)} payroll discussion",
            "recruitment_partner": f"Recap: {self._country_subject_label(lead.target_country)} placement support",
            "hris": f"Recap: {self._country_subject_label(lead.target_country)} HR operations discussion",
        }
        return subject_by_type.get(
            lead.lead_type or "",
            f"Recap: {self._country_subject_label(lead.target_country)} support discussion"
        )

    def _build_recap_email_body(
        self,
        lead: Lead,
        pipeline_record: PipelineRecord,
    ) -> str:
        summary_line = {
            "direct_eor": (
                f"Thanks again for the discussion today. From what you shared, the focus is hiring into {self._country_label(lead.target_country)} without getting slowed down by local entity setup."
            ),
            "direct_payroll": (
                f"Thanks again for the conversation today. From what you shared, the focus is getting compliant payroll in place for {self._country_label(lead.target_country)} without building unnecessary local overhead."
            ),
            "recruitment_partner": (
                f"Thanks again for the call today. It sounds like the focus is supporting placements into {self._country_label(lead.target_country)} with a dependable employment and payroll partner behind delivery."
            ),
            "hris": (
                f"Thanks again for the discussion today. It sounds like the focus is tightening HR operations and visibility for the team in {self._country_label(lead.target_country)}."
            ),
        }.get(
            lead.lead_type or "",
            "Thanks again for the discussion today. From what you shared, the focus is practical operational support."
        )

        next_step_line = {
            "new": "The next useful step would be to confirm scope, timeline, and decision process before we shape a proposal.",
            "contacted": "The next useful step would be to align on scope, timing, and any commercial constraints.",
            "replied": "The next useful step would be to convert the discussion into a defined commercial workstream and proposal outline.",
            "call_booked": "Ahead of the next discussion, we can structure the delivery model, commercials, and implementation approach.",
            "proposal": "We can now refine the proposal around scope, commercials, and any implementation questions.",
            "closed": "If priorities reopen, we can restart from the agreed commercial context.",
        }[pipeline_record.stage]

        closing_line = "If helpful, I can send over a concise support model and recommended next steps."
        return " ".join([f"Hi {lead.contact_name},", summary_line, next_step_line, closing_line])

    def _build_proposal_summary(
        self,
        lead: Lead,
        pipeline_record: PipelineRecord,
    ) -> str:
        return {
            "direct_eor": (
                f"Proposed model: GlobalKinect acts as employer of record in {self._country_label(lead.target_country)} so the client can hire faster, stay compliant, and avoid the upfront burden of setting up an entity first."
            ),
            "direct_payroll": (
                f"Proposed model: GlobalKinect manages compliant payroll processing and local payroll operations for employees in {self._country_label(lead.target_country)} with simpler execution and less operational burden."
            ),
            "recruitment_partner": (
                f"Proposed model: GlobalKinect supports recruiter-led placements in {self._country_label(lead.target_country)} by taking responsibility for compliant employment and payroll execution, helping the partner place talent faster without local employer complexity."
            ),
            "hris": (
                f"Proposed model: GlobalKinect supports HRIS-linked operating control, employee administration, and local people operations in {self._country_label(lead.target_country)} with better visibility and practical compliance support."
            ),
        }.get(
            lead.lead_type or "",
            f"Proposed model: GlobalKinect provides practical employment, payroll, and operational support in {self._country_label(lead.target_country)} with simpler execution and practical compliance support."
        )

    def _build_call_prep_summary_with_solution(
        self,
        lead: Lead,
        pipeline_record: PipelineRecord,
        solution_recommendation: SolutionRecommendation,
    ) -> str:
        priority_line = {
            "high": "This is a high-priority opportunity worth driving toward a defined next step on the call.",
            "medium": "Focus on confirming urgency, decision ownership, and practical buying criteria.",
            "low": "Use the call to confirm whether there is a real near-term project before investing more time.",
        }.get(pipeline_record.priority, "Use the call to qualify urgency and commercial fit.")

        country_label = self._country_label(lead.target_country)
        modules_label = ", ".join(solution_recommendation.recommended_modules)

        if solution_recommendation.sales_motion == "recruitment_partner":
            bundle_line = (
                f"Current fit: {solution_recommendation.bundle_label} for placements into {country_label}, "
                f"with {solution_recommendation.primary_module} as the entry point and modules across {modules_label}."
            )
        else:
            bundle_line = (
                f"Current fit: {solution_recommendation.bundle_label} in {country_label}, "
                f"with {solution_recommendation.primary_module} as the commercial entry point across {modules_label}."
            )

        return " ".join(
            [
                priority_line,
                bundle_line,
                self._strategy_line(solution_recommendation.commercial_strategy),
            ]
        )

    def _build_next_steps_message(
        self,
        lead: Lead,
        pipeline_record: PipelineRecord,
    ) -> str:
        return {
            "direct_eor": "I will send a simple EOR support outline and proposed next steps after we confirm hiring scope.",
            "direct_payroll": "I will send a concise payroll support outline and the information needed to move forward.",
            "recruitment_partner": "I will send a short placement support outline so we can align on how we would handle employment and payroll.",
            "hris": "I will send a short operating model and next-step plan so we can align on scope and implementation.",
        }.get(
            lead.lead_type or "",
            "I will send a concise support outline and recommended next steps."
        )

    def _build_recap_email_subject_with_solution(
        self,
        lead: Lead,
        solution_recommendation: SolutionRecommendation,
    ) -> str:
        return (
            f"Recap: {self._country_subject_label(lead.target_country)} "
            f"{solution_recommendation.bundle_label} support"
        )

    def _build_recap_email_body_with_solution(
        self,
        lead: Lead,
        pipeline_record: PipelineRecord,
        solution_recommendation: SolutionRecommendation,
    ) -> str:
        country_label = self._country_label(lead.target_country)
        modules_label = ", ".join(solution_recommendation.recommended_modules)
        summary_line = (
            f"Thanks again for the discussion today. From what you shared, the fit looks like "
            f"{solution_recommendation.bundle_label} support in {country_label}."
        )

        value_line = (
            f"That would give the team support across {modules_label}, with "
            f"{solution_recommendation.primary_module} as the commercial entry point."
        )

        next_step_line = {
            "new": "The next useful step would be to confirm scope, timing, and decision ownership before shaping the proposal.",
            "contacted": "The next useful step would be to align on scope, timing, and any commercial constraints.",
            "replied": "The next useful step would be to turn the discussion into a defined commercial workstream and proposal outline.",
            "call_booked": "Ahead of the next discussion, we can structure the delivery model, commercials, and implementation approach.",
            "proposal": "We can now refine the proposal around scope, commercials, and implementation details.",
            "closed": "If priorities reopen, we can restart from the agreed commercial context.",
        }[pipeline_record.stage]

        closing_line = (
            f"If useful, I can send over a concise {solution_recommendation.bundle_label} "
            "support model and recommended next steps."
        )
        return " ".join(
            [
                f"Hi {lead.contact_name},",
                summary_line,
                value_line,
                self._strategy_line(solution_recommendation.commercial_strategy),
                next_step_line,
                closing_line,
            ]
        )

    def _build_proposal_summary_with_solution(
        self,
        lead: Lead,
        solution_recommendation: SolutionRecommendation,
    ) -> str:
        country_label = self._country_label(lead.target_country)
        modules_label = ", ".join(solution_recommendation.recommended_modules)

        summary_by_bundle = {
            "EOR only": (
                f"Proposed model: GlobalKinect provides EOR support in {country_label} so the client can hire compliantly with simpler local execution."
            ),
            "Payroll only": (
                f"Proposed model: GlobalKinect provides payroll-only support in {country_label} so the team can run compliant payroll with less operational burden."
            ),
            "HRIS only": (
                f"Proposed model: GlobalKinect provides HRIS-led support in {country_label} so the team gains better HR visibility and operating control."
            ),
            "EOR + Payroll": (
                f"Proposed model: GlobalKinect provides an EOR + Payroll setup in {country_label} covering {modules_label}, so the client can hire faster and keep payroll execution aligned from day one."
            ),
            "Payroll + HRIS": (
                f"Proposed model: GlobalKinect provides a Payroll + HRIS setup in {country_label} covering {modules_label}, so the client gets compliant payroll plus stronger operational control."
            ),
            "EOR + HRIS": (
                f"Proposed model: GlobalKinect provides an EOR + HRIS setup in {country_label} covering {modules_label}, so the client can enter the market with compliant hiring and clearer HR structure."
            ),
            "Full Platform": (
                f"Proposed model: GlobalKinect provides a Full Platform setup in {country_label} covering {modules_label}, so the client can manage hiring, payroll, and HR operations through one operating model."
            ),
        }
        return summary_by_bundle[solution_recommendation.bundle_label]

    def _build_next_steps_message_with_solution(
        self,
        lead: Lead,
        solution_recommendation: SolutionRecommendation,
    ) -> str:
        return (
            f"I will send a concise {solution_recommendation.bundle_label} outline for "
            f"{self._country_label(lead.target_country)} so we can align on scope and next steps."
        )

    def _build_objection_response(
        self,
        lead: Lead,
        pipeline_record: PipelineRecord,
    ) -> str:
        return {
            "direct_eor": (
                "If you are considering setting up your own entity, the practical comparison is usually speed, compliance burden, and upfront cost. We can help you move sooner while keeping entity setup optional. Happy to show how this would work in practice."
            ),
            "direct_payroll": (
                "If another provider is being considered, the practical comparison is usually local execution quality, payroll reliability, and responsiveness. We can show exactly how we would manage that day to day. Happy to walk through the model in practice."
            ),
            "recruitment_partner": (
                "If timing is not final yet, we can stay lightweight and step in only when placements are ready. That keeps your delivery model flexible without creating local employer complexity. Happy to show how that would work in practice."
            ),
            "hris": (
                "If the team is not ready yet, we can scope the operating model first so the HRIS and local support pieces are ready when the project moves. Happy to outline the practical setup."
            ),
        }.get(
            lead.lead_type or "",
            "If timing or provider choice is still open, we can keep the next step light and focus on the most practical support model. Happy to show how this would work in practice."
        )

    def _build_objection_response_with_solution(
        self,
        lead: Lead,
        solution_recommendation: SolutionRecommendation,
    ) -> str:
        if solution_recommendation.sales_motion == "recruitment_partner":
            return (
                "If timing is still open, we can keep the partner model lightweight and step in only when placements are ready. "
                "That keeps delivery flexible without adding employer complexity. Happy to show how the model works in practice."
            )

        response_by_bundle = {
            "EOR only": (
                "If another provider is being considered, the useful comparison is speed, compliance coverage, and execution responsiveness. "
                "Happy to walk through how the EOR model would work in practice."
            ),
            "Payroll only": (
                "If another provider is being considered, the useful comparison is payroll reliability, local execution quality, and day-to-day responsiveness. "
                "Happy to show how the payroll model would work in practice."
            ),
            "HRIS only": (
                "If the team is not ready for a wider rollout yet, an HRIS-led model can still improve control without a heavy implementation step. "
                "Happy to outline the practical setup."
            ),
            "EOR + Payroll": (
                "If you may set up your own entity, the practical comparison is speed and execution. "
                "An EOR + Payroll model lets the team hire now and keep payroll live without waiting on the full entity timeline. "
                "Happy to show the setup in practice."
            ),
            "Payroll + HRIS": (
                "If the team is not ready for a wider platform yet, Payroll + HRIS can still give you compliant payroll plus stronger operational control without a large rollout. "
                "Happy to walk through the model."
            ),
            "EOR + HRIS": (
                "If timing is still open, an EOR + HRIS model can keep hiring moving while giving the team clearer HR structure from the start. "
                "Happy to show how that would work in practice."
            ),
            "Full Platform": (
                "If another provider is being considered, the useful comparison is whether one platform can cover employment, payroll, and HR control cleanly rather than fragmenting those workstreams. "
                "Happy to show how the full platform works in practice."
            ),
        }
        return response_by_bundle[solution_recommendation.bundle_label]

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
