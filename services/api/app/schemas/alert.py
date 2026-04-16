from datetime import datetime

from pydantic import BaseModel


class AlertHistoryItemOut(BaseModel):
    id: int
    game_id: int
    alert_type: str
    delivery_channel: str
    delivery_status: str
    sent_at: datetime
    provider_message_id: str | None = None
    metadata_json: dict | None = None
    game_external_id: str
    home_team_abbreviation: str
    away_team_abbreviation: str


class AlertHistoryResponse(BaseModel):
    items: list[AlertHistoryItemOut]


class DevTestAlertRequest(BaseModel):
    alert_type: str


class DevTestAlertResponse(BaseModel):
    id: int
    game_id: int
    alert_type: str
    delivery_status: str
