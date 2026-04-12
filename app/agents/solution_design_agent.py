from typing import List

from app.models.lead import Lead
from app.models.pipeline_record import PipelineRecord
from app.models.platform_terms import BundleLabel, PlatformModule, SalesMotion
from app.models.solution_recommendation import SolutionRecommendation
from app.utils.logger import get_logger
from app.utils.target_markets import country_label, is_primary_market

logger = get_logger(__name__)


class SolutionDesignAgent:
    def create_solution_recommendation(
        self,
        lead: Lead,
        pipeline_record: PipelineRecord | None = None,
    ) -> SolutionRecommendation:
        sales_motion = self._infer_sales_motion(lead)
        recommended_modules = self._determine_recommended_modules(
            lead,
            pipeline_record,
            sales_motion,
        )
        primary_module = self._determine_primary_module(lead, recommended_modules)
        bundle_label = self._build_bundle_label(recommended_modules)
        lead_reference = (
            pipeline_record.lead_reference
            if pipeline_record is not None
            else self._build_lead_reference(lead)
        )

        logger.info(
            f"Creating solution recommendation for {lead_reference}."
        )
        return SolutionRecommendation(
            lead_reference=lead_reference,
            company_name=lead.company_name,
            contact_name=lead.contact_name,
            target_country=lead.target_country or "unknown",
            sales_motion=sales_motion,
            recommended_modules=recommended_modules,
            primary_module=primary_module,
            bundle_label=bundle_label,
            commercial_strategy=self._build_commercial_strategy(
                lead,
                pipeline_record,
                sales_motion,
                bundle_label,
            ),
            rationale=self._build_rationale(
                lead,
                pipeline_record,
                sales_motion,
                recommended_modules,
                primary_module,
            ),
        )

    def create_solution_recommendations(
        self,
        leads: List[Lead],
        pipeline_records: List[PipelineRecord] | None = None,
    ) -> List[SolutionRecommendation]:
        if pipeline_records is not None and len(leads) != len(pipeline_records):
            raise ValueError("Lead and pipeline record counts must match.")

        logger.info(f"Creating {len(leads)} solution recommendations.")
        if pipeline_records is None:
            recommendations: List[SolutionRecommendation] = []
            for lead in leads:
                if lead.lead_type == "recruitment_partner":
                    logger.warning(
                        "recruitment_partner channel is discontinued — this lead should "
                        "be reclassified. Skipping outreach generation."
                    )
                    continue
                recommendations.append(self.create_solution_recommendation(lead))
        else:
            recommendations = []
            for lead, record in zip(leads, pipeline_records):
                if lead.lead_type == "recruitment_partner":
                    logger.warning(
                        "recruitment_partner channel is discontinued — this lead should "
                        "be reclassified. Skipping outreach generation."
                    )
                    continue
                recommendations.append(self.create_solution_recommendation(lead, record))
        logger.info("Solution recommendation creation completed.")
        return recommendations

    def _infer_sales_motion(self, lead: Lead) -> SalesMotion:
        if lead.lead_type == "recruitment_partner":
            return "recruitment_partner"
        return "direct_client"

    def _determine_recommended_modules(
        self,
        lead: Lead,
        pipeline_record: PipelineRecord | None,
        sales_motion: SalesMotion,
    ) -> list[PlatformModule]:
        if sales_motion == "recruitment_partner":
            return ["EOR", "Payroll"]

        if lead.lead_type == "direct_eor":
            if self._priority_value(lead, pipeline_record) == "high" and self._is_people_buyer(lead):
                return ["EOR", "Payroll", "HRIS"]
            return ["EOR", "Payroll"]

        if lead.lead_type == "direct_payroll":
            if self._is_primary_market(lead.target_country) and self._score_value(lead, pipeline_record) >= 8:
                return ["Payroll", "HRIS"]
            return ["Payroll"]

        if lead.lead_type == "hris":
            if self._is_primary_market(lead.target_country) and self._priority_value(lead, pipeline_record) != "low":
                return ["Payroll", "HRIS"]
            return ["HRIS"]

        if lead.recommended_angle and "entity" in lead.recommended_angle.lower():
            return ["EOR", "Payroll"]

        return ["Payroll"]

    def _determine_primary_module(
        self,
        lead: Lead,
        recommended_modules: list[PlatformModule],
    ) -> PlatformModule:
        primary_by_type = {
            "direct_eor": "EOR",
            "direct_payroll": "Payroll",
            "hris": "HRIS",
            "recruitment_partner": "EOR",
        }
        primary_module = primary_by_type.get(lead.lead_type or "")
        if primary_module:
            return primary_module
        return recommended_modules[0]

    def _build_bundle_label(
        self,
        recommended_modules: list[PlatformModule],
    ) -> BundleLabel:
        normalized_modules = tuple(sorted(recommended_modules))
        bundle_map: dict[tuple[str, ...], BundleLabel] = {
            ("EOR",): "EOR only",
            ("Payroll",): "Payroll only",
            ("HRIS",): "HRIS only",
            ("EOR", "Payroll"): "EOR + Payroll",
            ("HRIS", "Payroll"): "Payroll + HRIS",
            ("EOR", "HRIS"): "EOR + HRIS",
            ("EOR", "HRIS", "Payroll"): "Full Platform",
        }
        return bundle_map[normalized_modules]

    def _build_commercial_strategy(
        self,
        lead: Lead,
        pipeline_record: PipelineRecord | None,
        sales_motion: SalesMotion,
        bundle_label: BundleLabel,
    ) -> str:
        if sales_motion == "recruitment_partner":
            return (
                f"Lead with a partner-ready {bundle_label} offer that lets the recruiter "
                f"place talent into {self._country_label(lead.target_country)} without "
                "taking on employer or payroll complexity."
            )

        if bundle_label == "Full Platform":
            return (
                f"Position Global Kinect as a single operating platform for hiring, "
                f"payroll, and HR control in {self._country_label(lead.target_country)}."
            )

        if bundle_label == "EOR + Payroll":
            return (
                f"Position a fast market-entry bundle for {self._country_label(lead.target_country)} "
                "that combines compliant employment with payroll execution."
            )

        if bundle_label == "Payroll + HRIS":
            return (
                f"Position a payroll-led platform entry point for {self._country_label(lead.target_country)} "
                "with added operational visibility and control."
            )

        return (
            f"Lead with a focused {bundle_label} entry point in "
            f"{self._country_label(lead.target_country)} and expand into the wider platform as needed."
        )

    def _build_rationale(
        self,
        lead: Lead,
        pipeline_record: PipelineRecord | None,
        sales_motion: SalesMotion,
        recommended_modules: list[PlatformModule],
        primary_module: PlatformModule,
    ) -> str:
        modules_label = ", ".join(recommended_modules)
        buyer_context = (
            "partner-led hiring support"
            if sales_motion == "recruitment_partner"
            else "direct client expansion support"
        )
        angle = lead.recommended_angle or "practical GCC employment infrastructure support"
        return (
            f"Recommended because this lead currently looks like {buyer_context} into "
            f"{self._country_label(lead.target_country)}. The primary entry point is {primary_module}, "
            f"with {modules_label} proposed to match the current motion, priority "
            f"({self._priority_value(lead, pipeline_record)}), and angle: {angle}"
        )

    def _is_primary_market(self, target_country: str | None) -> bool:
        return is_primary_market(target_country)

    def _is_people_buyer(self, lead: Lead) -> bool:
        normalized_role = lead.contact_role.lower()
        return "people" in normalized_role or "hr" in normalized_role

    def _score_value(
        self,
        lead: Lead,
        pipeline_record: PipelineRecord | None,
    ) -> int:
        if pipeline_record is not None:
            return pipeline_record.score
        return lead.score or 0

    def _priority_value(
        self,
        lead: Lead,
        pipeline_record: PipelineRecord | None,
    ) -> str:
        if pipeline_record is not None:
            return pipeline_record.priority
        return lead.priority or "low"

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
