from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ProviderUsageOut(BaseModel):
    provider: str
    actual_calls: int
    success_calls: int
    error_calls: int
    rate_limited_calls: int
    expected_calls: int | None = None


class EndpointUsageOut(BaseModel):
    provider: str
    endpoint_key: str
    actual_calls: int
    success_calls: int
    error_calls: int
    rate_limited_calls: int


class ExpectedActualOut(BaseModel):
    expected: int
    actual: int


class ApiUsageSummaryOut(BaseModel):
    window: str
    totals: dict[str, int]
    expected_vs_actual: dict[str, ExpectedActualOut]
    by_provider: list[ProviderUsageOut]
    by_endpoint: list[EndpointUsageOut]


class ApiUsageTimeseriesPointOut(BaseModel):
    bucket_start: datetime
    provider: str
    actual_calls: int
    success_calls: int
    error_calls: int
    rate_limited_calls: int
    expected_calls: int | None = None


class ApiUsageTimeseriesOut(BaseModel):
    window: str
    bucket: str
    points: list[ApiUsageTimeseriesPointOut]


class IngestRunUsageOut(BaseModel):
    ingest_run_id: int
    started_at: datetime
    completed_at: datetime | None
    status: str
    poll_mode: str | None
    expected_espn_calls: int
    actual_espn_calls: int
    expected_odds_calls: int
    actual_odds_calls: int


class IngestRunUsageListOut(BaseModel):
    items: list[IngestRunUsageOut]
