from pydantic import BaseModel


class GameUpdateEvent(BaseModel):
    competition: str
