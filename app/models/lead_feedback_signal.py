from pydantic import BaseModel


class LeadFeedbackSignal(BaseModel):
    lead_reference: str | None = None
    company_name: str | None = None
    queue_status: str | None = None
    pipeline_stage: str | None = None
    outreach_status: str | None = None

    def blocks_duplicate_outreach(self) -> bool:
        queue_status = self._normalize(self.queue_status)
        pipeline_stage = self._normalize(self.pipeline_stage)
        outreach_status = self._normalize(self.outreach_status)

        return (
            queue_status in {"approved", "sent", "hold"}
            or pipeline_stage in {"contacted", "replied", "callbooked", "proposal", "closed"}
            or outreach_status in {"approved", "sent"}
        )

    def score_adjustment(self) -> int:
        queue_status = self._normalize(self.queue_status)
        pipeline_stage = self._normalize(self.pipeline_stage)
        outreach_status = self._normalize(self.outreach_status)

        adjustment = 0
        if queue_status == "hold":
            adjustment -= 3
        elif queue_status in {"approved", "sent"}:
            adjustment -= 2

        if pipeline_stage in {"replied", "callbooked", "proposal", "closed"}:
            adjustment -= 2
        elif pipeline_stage == "contacted":
            adjustment -= 1

        if outreach_status == "sent":
            adjustment -= 1
        elif outreach_status == "approved":
            adjustment -= 1

        return max(-4, adjustment)

    def summary(self) -> str:
        parts: list[str] = []
        if self.queue_status:
            parts.append(f"queue={self.queue_status}")
        if self.pipeline_stage:
            parts.append(f"stage={self.pipeline_stage}")
        if self.outreach_status:
            parts.append(f"outreach={self.outreach_status}")
        return ", ".join(parts) if parts else "existing sales activity"

    def _normalize(self, value: str | None) -> str:
        if not value:
            return ""
        return "".join(character for character in value.lower() if character.isalnum())
