from typing import Optional

from pydantic import BaseModel


class RemStatus(BaseModel):
    status: str
    frequency_peak: Optional[str] = None
    frequency_off_peak: Optional[str] = None
    alert: Optional[str] = None
    monitored_status: Optional[str] = None
    is_outage: bool = False
    direction: str
    language: str
    is_holiday: bool = False
