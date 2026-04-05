from app.agents.outreach_review_agent import OutreachReviewAgent
from app.models.lead_feedback_signal import LeadFeedbackSignal
from app.models.pipeline_record import PipelineRecord


def _build_pipeline_record(
    *,
    lead_reference: str = "Guidepoint|Unknown Contact|the UAE|direct_payroll",
    stage: str = "new",
    outreach_status: str = "drafted",
    next_action: str = "review_and_send_message",
    notes: str | None = None,
) -> PipelineRecord:
    return PipelineRecord(
        lead_reference=lead_reference,
        company_name="Guidepoint",
        contact_name="Unknown Contact",
        lead_type="direct_payroll",
        target_country="United Arab Emirates",
        score=8,
        priority="high",
        sales_motion="direct_client",
        primary_module="Payroll",
        bundle_label="Payroll + HRIS",
        recommended_modules=["Payroll", "HRIS"],
        stage=stage,
        outreach_status=outreach_status,
        next_action=next_action,
        notes=notes,
    )


class FakeNotionService:
    def __init__(self, signals: list[LeadFeedbackSignal]) -> None:
        self._signals = signals
        self.upserted_pipeline_records: list[PipelineRecord] = []

    def is_outreach_queue_configured(self) -> bool:
        return True

    def is_configured(self) -> bool:
        return True

    def fetch_outreach_queue_feedback_signals(
        self,
        limit: int = 200,
    ) -> list[LeadFeedbackSignal]:
        return self._signals[:limit]

    def upsert_pipeline_pages(self, records: list[PipelineRecord]) -> list[dict[str, str]]:
        self.upserted_pipeline_records.extend(records)
        return [{"id": "pipeline-page"} for _ in records]


class FakeSupabaseService:
    def __init__(self, records: dict[str, PipelineRecord]) -> None:
        self._records = records
        self.updated_records: list[PipelineRecord] = []

    def is_configured(self) -> bool:
        return True

    def fetch_pipeline_record_by_lead_reference(
        self,
        lead_reference: str,
    ) -> PipelineRecord | None:
        return self._records.get(lead_reference)

    def update_pipeline_record(self, record: PipelineRecord) -> dict[str, str]:
        self.updated_records.append(record)
        self._records[record.lead_reference] = record
        return {"status": "ok"}


def test_sync_queue_decisions_marks_approved_and_updates_pipeline_and_notion() -> None:
    lead_reference = "Guidepoint|Unknown Contact|the UAE|direct_payroll"
    record = _build_pipeline_record(lead_reference=lead_reference)
    notion_service = FakeNotionService(
        [LeadFeedbackSignal(lead_reference=lead_reference, queue_status="Approved")]
    )
    supabase_service = FakeSupabaseService({lead_reference: record})
    agent = OutreachReviewAgent(
        notion_service=notion_service,
        supabase_service=supabase_service,
    )

    result = agent.sync_queue_decisions(limit=10)

    assert result.reviewed_count == 1
    assert result.approved_count == 1
    assert result.skipped_count == 0
    updated_record = supabase_service.updated_records[0]
    assert updated_record.outreach_status == "approved"
    assert updated_record.next_action == "send_message"
    assert notion_service.upserted_pipeline_records[0].outreach_status == "approved"


def test_sync_queue_decisions_marks_sent_and_advances_pipeline() -> None:
    lead_reference = "Guidepoint|Unknown Contact|the UAE|direct_payroll"
    record = _build_pipeline_record(lead_reference=lead_reference)
    notion_service = FakeNotionService(
        [LeadFeedbackSignal(lead_reference=lead_reference, queue_status="Sent")]
    )
    supabase_service = FakeSupabaseService({lead_reference: record})
    agent = OutreachReviewAgent(
        notion_service=notion_service,
        supabase_service=supabase_service,
    )

    result = agent.sync_queue_decisions(limit=10)

    assert result.reviewed_count == 1
    assert result.sent_count == 1
    updated_record = supabase_service.updated_records[0]
    assert updated_record.outreach_status == "sent"
    assert updated_record.stage == "contacted"
    assert updated_record.next_action == "wait_for_reply"
    assert updated_record.last_outreach_at is not None


def test_sync_queue_decisions_marks_hold_and_sets_operator_hold() -> None:
    lead_reference = "Guidepoint|Unknown Contact|the UAE|direct_payroll"
    record = _build_pipeline_record(lead_reference=lead_reference, outreach_status="approved")
    notion_service = FakeNotionService(
        [LeadFeedbackSignal(lead_reference=lead_reference, queue_status="Hold")]
    )
    supabase_service = FakeSupabaseService({lead_reference: record})
    agent = OutreachReviewAgent(
        notion_service=notion_service,
        supabase_service=supabase_service,
    )

    result = agent.sync_queue_decisions(limit=10)

    assert result.reviewed_count == 1
    assert result.hold_count == 1
    updated_record = supabase_service.updated_records[0]
    assert updated_record.outreach_status == "approved"
    assert updated_record.next_action == "operator_hold"
    assert updated_record.notes is not None
    assert "Hold in Outreach Queue" in updated_record.notes


def test_sync_queue_decisions_skips_stale_queue_status_when_pipeline_is_further_along() -> None:
    lead_reference = "Guidepoint|Unknown Contact|the UAE|direct_payroll"
    record = _build_pipeline_record(
        lead_reference=lead_reference,
        stage="contacted",
        outreach_status="sent",
        next_action="wait_for_reply",
    )
    notion_service = FakeNotionService(
        [LeadFeedbackSignal(lead_reference=lead_reference, queue_status="Approved")]
    )
    supabase_service = FakeSupabaseService({lead_reference: record})
    agent = OutreachReviewAgent(
        notion_service=notion_service,
        supabase_service=supabase_service,
    )

    result = agent.sync_queue_decisions(limit=10)

    assert result.reviewed_count == 1
    assert result.skipped_count == 1
    assert not supabase_service.updated_records
    assert not notion_service.upserted_pipeline_records
