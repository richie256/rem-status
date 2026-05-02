import json
import os
import time
from datetime import datetime
from typing import Optional

import httpx
from bs4 import BeautifulSoup
from loguru import logger

from .config import Settings
from .models import RemStatus

CACHE_FILE = "rem_cache.json"
CACHE_EXPIRY = 48 * 3600  # 48 hours for frequency

STATIONS = [
    "Brossard",
    "Du Quartier",
    "Panama",
    "Île-des-Sœurs",
    "Gare Centrale",
    "McGill",
    "Édouard-Montpetit",
    "Canora",
    "Ville-de-Mont-Royal",
    "Côte-de-Liesse",
    "Montpellier",
    "Du Ruisseau",
    "Bois-Franc",
    "Sunnybrooke",
    "Pierrefonds-Roxboro",
    "Île-Bigras",
    "Sainte-Dorothée",
    "Grand-Moulin",
    "Deux-Montagnes",
]


class RemScraper:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = httpx.AsyncClient(timeout=10.0)

    def _get_cache(self) -> dict:
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error reading cache: {e}")
        return {"timestamp": 0, "frequency": None, "holiday_date": None, "is_holiday": False}

    def _save_cache(self, cache: dict):
        try:
            with open(CACHE_FILE, "w") as f:
                json.dump(cache, f)
        except Exception as e:
            logger.error(f"Error saving cache: {e}")

    async def fetch_status(self) -> Optional[RemStatus]:
        try:
            # 1. Fetch status (always needed for alerts/status)
            status_resp = await self.client.get(self.settings.status_url)
            status_resp.raise_for_status()
            status_soup = BeautifulSoup(status_resp.text, "html.parser")
            status = self._parse_status(status_soup)

            # 2. Manage cache
            cache = self._get_cache()
            now = datetime.now()
            today_str = now.strftime("%Y-%m-%d")

            # 3. Handle frequency
            if cache["frequency"] and (time.time() - cache["timestamp"] < CACHE_EXPIRY):
                peak, off_peak = cache["frequency"]["peak"], cache["frequency"]["off_peak"]
            else:
                sched_resp = await self.client.get(self.settings.schedule_url)
                sched_resp.raise_for_status()
                sched_soup = BeautifulSoup(sched_resp.text, "html.parser")
                peak, off_peak = self._parse_frequencies(sched_soup)
                cache["timestamp"] = time.time()
                cache["frequency"] = {"peak": peak, "off_peak": off_peak}

            # 4. Handle holiday
            if cache["holiday_date"] == today_str:
                is_holiday = cache["is_holiday"]
            else:
                is_holiday = self._is_today_holiday(status_soup)
                cache["holiday_date"] = today_str
                cache["is_holiday"] = is_holiday

            self._save_cache(cache)

            alert = self._parse_alert(status_soup)

            is_outage, monitored_status = self._check_outage(status, alert, status_soup)

            return RemStatus(
                status=status,
                frequency_peak=peak,
                frequency_off_peak=off_peak,
                alert=alert,
                monitored_status=monitored_status,
                is_outage=is_outage,
                direction=self.settings.direction,
                language=self.settings.language,
                is_holiday=is_holiday,
            )
        except Exception as e:
            logger.error(f"Error fetching REM status: {e}")
            return None

    def _check_outage(self, status: str, alert: Optional[str], soup: BeautifulSoup) -> tuple[bool, str]:
        # Normal status strings
        normal_strings = ["normal", "service normal", "normal - service", "service - normal"]

        is_global_normal = status.lower() in normal_strings and (not alert or alert.lower() in normal_strings)

        # If we have an issue, check if it's in the monitored range
        from_st = self.settings.monitor_station_from
        to_st = self.settings.monitor_station_to

        if not from_st or not to_st:
            # Report any outage if not specifically monitoring a range
            return not is_global_normal, alert or status

        # Determine stations in range
        try:
            stations_lower = [s.lower() for s in STATIONS]
            idx_from = stations_lower.index(from_st.lower())
            idx_to = stations_lower.index(to_st.lower())

            start = min(idx_from, idx_to)
            end = max(idx_from, idx_to)
            monitored_range = STATIONS[start : end + 1]
            monitored_range_lower = [s.lower() for s in monitored_range]
        except ValueError:
            # If stations not found, fallback to reporting any outage but log it
            logger.warning(f"Station {from_st} or {to_st} not found in station list.")
            return not is_global_normal, alert or status

        # 1. Check the map status indicators (most reliable for specific stations)
        station_items = soup.select(".station-item")
        out_stations = []
        for item in station_items:
            name_el = item.select_one(".station-name")
            if not name_el:
                continue
            name = name_el.get_text(strip=True).lower()
            
            if name in monitored_range_lower:
                # Check for "out-service" or missing "in-service"
                status_span = item.select_one(".item-img span")
                if status_span:
                    classes = status_span.get("class", [])
                    # If it has 'out-service' or doesn't have 'in-service' (and it's not 'elevator-status')
                    if "out-service" in classes or ("in-service" not in classes and "elevator-status" not in classes):
                        out_stations.append(name_el.get_text(strip=True))

        if out_stations:
            return True, f"Outage at stations: {', '.join(out_stations)}"

        # 2. Check if alert or status mentions any station in range (fallback/text alerts)
        full_text = f"{status} {alert or ''}".lower()

        # If the alert mentions "all stations" or "network wide"
        network_wide_keywords = [
            "réseau",
            "network",
            "toutes les stations",
            "all stations",
            "complete network",
            "ensemble du réseau",
        ]
        if any(kw in full_text for kw in network_wide_keywords):
            return True, alert or status

        for st in monitored_range_lower:
            if st in full_text:
                return True, alert or status

        # If it's an outage but not in our range
        if not is_global_normal:
            return False, "Normal (Outage elsewhere)"
            
        return False, "Normal"

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
        # Collect all potential alert messages
        alert_selectors = [
            ".live-network-status__alert-content",
            ".live-network-status__trip-details-text",
            ".alert-message",
            ".status-alert",
            ".status-indicator",
        ]
        
        found_texts = []
        for selector in alert_selectors:
            elements = soup.select(selector)
            for el in elements:
                text = el.get_text(strip=True)
                if text and text not in found_texts:
                    # Filter out generic "normal" messages
                    if not any(kw in text.lower() for kw in ["service normal", "service - normal"]):
                        found_texts.append(text)

        if found_texts:
            return " | ".join(found_texts)

        return None

    async def close(self):
        await self.client.aclose()
