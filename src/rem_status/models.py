from typing import Optional

from pydantic import BaseModel


class RemStatus(BaseModel):
    status: str
    frequency_peak: Optional[str] = None
    frequency_off_peak: Optional[str] = None
    alert: Optional[str] = None
    direction: str
    language: str
    is_holiday: bool = False
