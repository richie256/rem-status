from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    mqtt_host: str = "localhost"
    mqtt_port: int = 1883
    mqtt_username: Optional[str] = None
    mqtt_password: Optional[str] = None
    mqtt_discovery_prefix: str = "homeassistant"
    mqtt_base_topic: str = "rem_status"

    direction: str = "Entre Brossard et Bois-Franc"
    language: str = "fr"
    poll_interval_peak: int = 600  # 10 minutes
    poll_interval_off_peak: int = 1800  # 300 minutes (Wait, user said 30 mins) -> 1800s

    # Peak hours: 6:30-9:30 and 15:30-18:30 (typical REM peak)
    peak_morning_start: str = "06:30"
    peak_morning_end: str = "09:30"
    peak_afternoon_start: str = "15:30"
    peak_afternoon_end: str = "18:30"

    def get_poll_interval(self, is_holiday: bool = False) -> int:
        from datetime import datetime, time
        now_dt = datetime.now()
        now = now_dt.time()
        
        # Sundays are treated like holidays in terms of frequency
        is_sunday = now_dt.weekday() == 6
        if is_holiday or is_sunday:
            return self.poll_interval_off_peak

        def is_between(start_str, end_str):
            start = time.fromisoformat(start_str)
            end = time.fromisoformat(end_str)
            return start <= now <= end

        if is_between(self.peak_morning_start, self.peak_morning_end) or \
           is_between(self.peak_afternoon_start, self.peak_afternoon_end):
            return self.poll_interval_peak
        return self.poll_interval_off_peak

    @property
    def url(self) -> str:
        if self.language.lower() == "en":
            return "https://rem.info/en/se-deplacer/horaire-de-service"
        return "https://rem.info/fr/se-deplacer/horaire-de-service"
