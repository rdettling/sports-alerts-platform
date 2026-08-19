from datetime import datetime

from pydantic import BaseModel


class AlertDeliveryOut(BaseModel):
    channel: str
    status: str
    attempted_at: datetime | None = None


class AlertHistoryItemOut(BaseModel):
    id: int
    game_id: int
    alert_type: str
    triggered_at: datetime
    game_external_id: str
    home_team_abbreviation: str
    away_team_abbreviation: str
    deliveries: list[AlertDeliveryOut]


class AlertHistoryResponse(BaseModel):
    items: list[AlertHistoryItemOut]


class DevTestAlertRequest(BaseModel):
    league: str
    alert_type: str


class DevTestAlertResponse(BaseModel):
    id: int
    game_id: int
    league: str
    alert_type: str
    deliveries: list[AlertDeliveryOut]
