from pydantic import BaseModel
from typing import Optional

class Song(BaseModel):
    title: str
    original_url: str
    url: Optional[str] = None