from pydantic import BaseModel


class RemStatus(BaseModel):
    status: str
    frequency_peak: str | None = None
    frequency_off_peak: str | None = None
    alert: str | None = None
    monitored_status: str | None = None
    is_outage: bool = False
    direction: str
    language: str
    is_holiday: bool = False
