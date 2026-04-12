from typing import List

from app.agents.lead_feedback_agent import LeadFeedbackAgent, LeadFeedbackIndex
from app.models.lead import Lead
from app.utils.target_markets import market_score, normalize_target_country
from app.utils.logger import get_logger

logger = get_logger(__name__)


class LeadScoringAgent:
    def __init__(self, lead_feedback_agent: LeadFeedbackAgent | None = None) -> None:
        self.lead_feedback_agent = lead_feedback_agent or LeadFeedbackAgent()

    def score_leads(
        self,
        leads: List[Lead],
        feedback_index: LeadFeedbackIndex | None = None,
    ) -> List[Lead]:
        logger.info(f"Scoring {len(leads)} leads.")
        scored_leads = [
            self._score_lead(lead, feedback_index=feedback_index)
            for lead in leads
        ]
        logger.info("Lead scoring completed.")
        return scored_leads

    def _score_lead(
        self,
        lead: Lead,
        *,
        feedback_index: LeadFeedbackIndex | None = None,
    ) -> Lead:
        score = 0

        score += self._score_target_country(lead.target_country)
        score += self._score_company_country(lead.company_country)
        score += self._score_lead_type(lead.lead_type)
        score += self._score_contact_role(lead.contact_role)

        if lead.email:
            score += 1

        if lead.linkedin_url:
            score += 1

        feedback_summary = None
        if feedback_index is not None:
            signal = self.lead_feedback_agent.signal_for_lead(feedback_index, lead)
            if signal is not None:
                score += signal.score_adjustment()
                feedback_summary = f"Existing sales activity detected: {signal.summary()}."

        final_score = max(1, min(score, 10))
        priority = self._priority_for_score(final_score)
        recommended_angle = self._recommended_angle_for_lead(lead)

        return lead.model_copy(
            update={
                "score": final_score,
                "priority": priority,
                "recommended_angle": recommended_angle,
                "feedback_summary": feedback_summary,
            }
        )

    def _score_target_country(self, target_country: str | None) -> int:
        return market_score(target_country)

    def _score_company_country(self, company_country: str | None) -> int:
        country_scores = {
            "United Kingdom": 2,
            "Germany": 2,
            "France": 1,
            "Netherlands": 1,
        }
        return country_scores.get(company_country or "", 0)

    def _score_lead_type(self, lead_type: str | None) -> int:
        lead_type_scores = {
            "direct_eor": 3,
            "direct_payroll": 3,
            "recruitment_partner": 3,
            "hris": 2,
        }
        return lead_type_scores.get(lead_type or "", 0)

    def _score_contact_role(self, contact_role: str) -> int:
        normalized_role = contact_role.lower()

        if "founder" in normalized_role:
            return 2
        if "head of people" in normalized_role or "people" in normalized_role:
            return 2
        if "director" in normalized_role:
            return 2
        return 1

    def _priority_for_score(self, score: int) -> str:
        if score >= 8:
            return "high"
        if score >= 5:
            return "medium"
        return "low"

    def _recommended_angle_for_lead(self, lead: Lead) -> str:
        target_country = normalize_target_country(lead.target_country)
        angle_by_type = {
            "direct_eor": "Position Global Kinect around hiring into market without waiting for local entity setup.",
            "direct_payroll": (
                "Lead with payroll compliance, local processing confidence, and "
                "regional execution support."
                if target_country and market_score(target_country) < 3
                else "Lead with payroll compliance, local processing confidence, and GCC execution support."
            ),
            "recruitment_partner": "Position Global Kinect as the employment and payroll partner behind recruiter-led placements.",
            "hris": "Lead with stronger HRIS control, employee visibility, and operational consistency across markets.",
        }

        return angle_by_type.get(
            lead.lead_type or "",
            "Lead with practical support across EOR, payroll, and people operations."
        )
