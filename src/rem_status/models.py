from pydantic import BaseModel
from typing import Optional


class RemStatus(BaseModel):
    status: str
    frequency_peak: Optional[str] = None
    frequency_off_peak: Optional[str] = None
    alert: Optional[str] = None
    direction: str
    language: str
    is_holiday: bool = False
