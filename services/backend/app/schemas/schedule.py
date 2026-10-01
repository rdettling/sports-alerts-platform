from typing import Literal

from pydantic import AwareDatetime, BaseModel

JobType = Literal["catalog_sync", "live_sync", "odds_sync"]
JobState = Literal["awaiting_first_result", "queued", "scheduled", "live", "waiting_for_start", "no_upcoming", "retry_scheduled", "budget_limited"]


class ScheduledJobOut(BaseModel):
    competition: str
    job_type: JobType
    next_run_at: AwareDatetime | None
    last_success_at: AwareDatetime | None = None
    state: JobState


class ScheduleSnapshot(BaseModel):
    reported_at: AwareDatetime
    next_catalog_at: AwareDatetime
    jobs: list[ScheduledJobOut]
