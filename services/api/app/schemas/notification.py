from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


DeliveryMode = Literal["email", "push", "both"]


class NotificationSettingsOut(BaseModel):
    delivery_mode: DeliveryMode
    subscription_count: int
    push_configured: bool
    vapid_public_key: str | None


class UpdateNotificationSettingsRequest(BaseModel):
    delivery_mode: DeliveryMode


class PushSubscriptionKeys(BaseModel):
    p256dh: str = Field(min_length=16, max_length=255)
    auth: str = Field(min_length=8, max_length=255)


class PushSubscriptionRequest(BaseModel):
    endpoint: HttpUrl
    keys: PushSubscriptionKeys


class DeletePushSubscriptionRequest(BaseModel):
    endpoint: HttpUrl
