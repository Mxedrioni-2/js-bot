from pydantic import BaseModel
from typing import Optional
from models.song import Song


class GuildState(BaseModel):
    loop_state: int = 0
    current_song: Optional[Song] = None
    last_activity: float = 0.0
    volume: float = 1.0