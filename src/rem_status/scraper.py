import httpx
import json
import time
import os
from datetime import datetime
from bs4 import BeautifulSoup
from loguru import logger
from typing import Optional
from .models import RemStatus
from .config import Settings

CACHE_FILE = "frequency_cache.json"
CACHE_EXPIRY = 48 * 3600  # 48 hours


class RemScraper:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = httpx.AsyncClient(timeout=10.0)

    def _get_cached_frequencies(self) -> Optional[dict]:
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, "r") as f:
                    cache = json.load(f)
                    if time.time() - cache["timestamp"] < CACHE_EXPIRY:
                        return cache["data"]
            except Exception as e:
                logger.error(f"Error reading cache: {e}")
        return None

    def _save_cached_frequencies(self, peak: str, off_peak: str):
        try:
            with open(CACHE_FILE, "w") as f:
                json.dump({"timestamp": time.time(), "data": {"peak": peak, "off_peak": off_peak}}, f)
        except Exception as e:
            logger.error(f"Error saving cache: {e}")

    async def fetch_status(self) -> Optional[RemStatus]:
        try:
            response = await self.client.get(self.settings.url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")

            status = self._parse_status(soup)

            cached = self._get_cached_frequencies()
            if cached:
                peak, off_peak = cached["peak"], cached["off_peak"]
                logger.debug("Using cached frequency data.")
            else:
                peak, off_peak = self._parse_frequencies(soup)
                if peak and off_peak:
                    self._save_cached_frequencies(peak, off_peak)
                    logger.debug("Cached new frequency data.")

            alert = self._parse_alert(soup)
            is_holiday = self._is_today_holiday(soup)

            return RemStatus(
                status=status,
                frequency_peak=peak,
                frequency_off_peak=off_peak,
                alert=alert,
                direction=self.settings.direction,
                language=self.settings.language,
                is_holiday=is_holiday,
            )
        except Exception as e:
            logger.error(f"Error fetching REM status: {e}")
            return None

    def _is_today_holiday(self, soup: BeautifulSoup) -> bool:
        now = datetime.now()

        # Months in French and English
        months_fr = [
            "janvier",
            "février",
            "mars",
            "avril",
            "mai",
            "juin",
            "juillet",
            "août",
            "septembre",
            "octobre",
            "novembre",
            "décembre",
        ]
        months_en = [
            "january",
            "february",
            "march",
            "april",
            "may",
            "june",
            "july",
            "august",
            "september",
            "october",
            "november",
            "december",
        ]

        day = now.day
        month_fr = months_fr[now.month - 1]
        month_en = months_en[now.month - 1]

        # Search for holiday blocks (usually titled "Jours fériés" or "Holidays")
        holiday_keywords = ["férié", "holiday"]
        blocks = soup.select(".block, .views-element-container, .field__item")

        for block in blocks:
            text = block.get_text().lower()
            if any(kw in text for kw in holiday_keywords):
                # Search for today's date in the text (e.g., "13 avril" or "April 13")
                today_fr = f"{day} {month_fr}"
                today_en = f"{month_en} {day}"
                if today_fr in text or today_en in text:
                    logger.info(f"Today ({today_fr}/{today_en}) detected as a holiday!")
                    return True

        return False

    def _parse_status(self, soup: BeautifulSoup) -> str:
        # Based on search results, look for service-status-banner or similar
        status_banner = soup.select_one(".service-status-banner")
        if status_banner:
            return status_banner.get_text(strip=True)

        # Fallback to general status block if exists
        status_block = soup.select_one(".block-rem-service-status")
        if status_block:
            return status_block.get_text(strip=True)

        return "Normal" if self.settings.language == "fr" else "Normal"

    def _parse_frequencies(self, soup: BeautifulSoup) -> tuple[Optional[str], Optional[str]]:
        peak = None
        off_peak = None

        # Look for frequency values
        # The structure found is: <h6>Frequency value</h6>
        # We need to adapt the logic to find these h6 values.
        # Since the structure is quite simple, we can select all h6 and find the ones that match frequency patterns.
        h6_elements = soup.select("h6")
        logger.debug(f"Found {len(h6_elements)} h6 elements: {[h.get_text(strip=True) for h in h6_elements]}")
        frequencies = []
        for h6 in h6_elements:
            text = h6.get_text(strip=True).lower()
            if "min" in text:
                frequencies.append(h6.get_text(strip=True))

        if len(frequencies) >= 2:
            peak = frequencies[0]
            off_peak = frequencies[1]

        return peak, off_peak

    def _parse_alert(self, soup: BeautifulSoup) -> Optional[str]:
        alert_block = soup.select_one(".alert-message, .status-alert, .status-indicator")
        if alert_block:
            text = alert_block.get_text(strip=True)
            # If it's just "Normal", it's not really an alert we want to highlight separately
            if text.lower() in ["normal", "service normal"]:
                return None
            return text
        return None

    async def close(self):
        await self.client.aclose()
