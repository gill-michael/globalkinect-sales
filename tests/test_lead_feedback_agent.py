from app.agents.lead_feedback_agent import LeadFeedbackAgent
from app.models.lead import Lead
from app.models.lead_feedback_signal import LeadFeedbackSignal


class _FakeNotionService:
    def __init__(self, queue_signals=None, pipeline_signals=None, configured=True, outreach_configured=True):
        self._queue_signals = queue_signals or []
        self._pipeline_signals = pipeline_signals or []
        self._configured = configured
        self._outreach_configured = outreach_configured

    def is_configured(self) -> bool:
        return self._configured

    def is_outreach_queue_configured(self) -> bool:
        return self._outreach_configured

    def fetch_outreach_queue_feedback_signals(self, limit: int = 200):
        return self._queue_signals[:limit]

    def fetch_pipeline_feedback_signals(self, limit: int = 200):
        return self._pipeline_signals[:limit]


def test_collect_feedback_index_merges_queue_and_pipeline_signals() -> None:
    notion_service = _FakeNotionService(
        queue_signals=[
            LeadFeedbackSignal(
                lead_reference="Guidepoint|Unknown Contact|the UAE|direct_payroll",
                company_name="Guidepoint",
                queue_status="Approved",
            )
        ],
        pipeline_signals=[
            LeadFeedbackSignal(
                lead_reference="Guidepoint|Unknown Contact|the UAE|direct_payroll",
                company_name="Guidepoint",
                pipeline_stage="proposal",
                outreach_status="sent",
            )
        ],
    )
    agent = LeadFeedbackAgent(notion_service=notion_service)

    feedback_index = agent.collect_feedback_index()
    signal = feedback_index.find(
        lead_reference="Guidepoint|Unknown Contact|the UAE|direct_payroll",
        company_name="Guidepoint",
    )

    assert signal is not None
    assert signal.queue_status == "Approved"
    assert signal.pipeline_stage == "proposal"
    assert signal.outreach_status == "sent"
    assert signal.blocks_duplicate_outreach() is True


def test_signal_for_lead_falls_back_to_company_name() -> None:
    notion_service = _FakeNotionService(
        pipeline_signals=[
            LeadFeedbackSignal(
                company_name="Guidepoint",
                pipeline_stage="contacted",
            )
        ]
    )
    agent = LeadFeedbackAgent(notion_service=notion_service)
    feedback_index = agent.collect_feedback_index()

    signal = agent.signal_for_lead(
        feedback_index,
        Lead(
            company_name="Guidepoint",
            contact_name="Unknown Contact",
            contact_role="Unknown Role",
            target_country="United Arab Emirates",
            lead_type="direct_payroll",
        ),
    )

    assert signal is not None
    assert signal.pipeline_stage == "contacted"
