from datetime import datetime

from pydantic import BaseModel


class SportsUpdateOut(BaseModel):
    id: int
    title: str
    summary: str | None
    article_url: str
    source_name: str
    published_at: datetime | None
    league: str
    scope: str
    importance: str
    confidence: str | None
    tags: list[str]
    reason: str | None
    team_abbreviations: list[str]
    matched_scope: str


class SportsUpdatesFeedOut(BaseModel):
    items: list[SportsUpdateOut]
