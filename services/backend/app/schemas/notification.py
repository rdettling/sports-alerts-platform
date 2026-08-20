from pydantic import BaseModel, Field, HttpUrl


class NotificationSettingsOut(BaseModel):
    email_alerts_enabled: bool
    push_subscription_count: int
    push_configured: bool
    vapid_public_key: str | None


class UpdateNotificationSettingsRequest(BaseModel):
    email_alerts_enabled: bool


class PushSubscriptionKeys(BaseModel):
    p256dh: str = Field(min_length=16, max_length=255)
    auth: str = Field(min_length=8, max_length=255)


class PushSubscriptionRequest(BaseModel):
    endpoint: HttpUrl
    keys: PushSubscriptionKeys


class PushSubscriptionEndpointRequest(BaseModel):
    endpoint: HttpUrl


class PushSubscriptionStatusOut(BaseModel):
    is_subscribed: bool
