from typing import Literal

from pydantic import BaseModel, Field

from app.utils.time import utc_now_iso

ExecutionTaskType = Literal[
    "draft_message",
    "send_message",
    "wait_for_reply",
    "nudge_message",
    "book_call",
    "prepare_call",
    "follow_up",
    "escalate_follow_up",
]
ExecutionTaskStatus = Literal["open", "completed", "cancelled"]


class ExecutionTask(BaseModel):
    lead_reference: str
    company_name: str | None = None
    company_canonical: str | None = None
    task_type: ExecutionTaskType
    description: str
    priority: str
    due_in_days: int
    status: ExecutionTaskStatus = "open"
    created_at: str = Field(default_factory=utc_now_iso)
