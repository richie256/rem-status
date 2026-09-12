from unittest.mock import AsyncMock, patch

import pytest

from rem_status.config import Settings
from rem_status.scraper import RemScraper


@pytest.fixture
def settings():
    return Settings(language="fr")


@pytest.fixture
def scraper(settings, tmp_path):
    cache_file = tmp_path / "test_cache.json"
    return RemScraper(settings, cache_file=str(cache_file))


@pytest.mark.asyncio
async def test_fetch_status_mock(scraper):
    mock_html = """
    <html>
        <body>
            <a data-tab="tab-service" class="live-network-status__tab-link">
                <span aria-label="normal service"></span>
            </a>
            <div id="tab-service"></div>
            <div id="tab-interruption"></div>
            <h6>3 min 30 s</h6>
            <h6>7 min</h6>
        </body>
    </html>
    """
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.return_value = AsyncMock(status_code=200, text=mock_html)
        mock_get.return_value.raise_for_status = lambda: None

        status = await scraper.fetch_status()

        assert status is not None
        assert status.status == "Normal"
        assert status.frequency_peak == "3 min 30 s"
        assert status.frequency_off_peak == "7 min"
        assert status.direction == "Entre Brossard et Bois-Franc"


@pytest.mark.asyncio
async def test_holiday_detection(scraper):
    from datetime import datetime

    # Mock date to April 13
    with patch("rem_status.scraper.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2026, 4, 13)
        mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

        mock_html = """
        <html>
            <body>
                <a data-tab="tab-service" class="live-network-status__tab-link">
                    <span aria-label="normal service"></span>
                </a>
                <div id="tab-service"></div>
                <div id="tab-interruption"></div>
                <div class="block">
                    <h2>Jours fériés</h2>
                    <p>Le service sera hors pointe les jours suivants : 13 avril, 1er mai.</p>
                </div>
            </body>
        </html>
        """

        with patch("httpx.AsyncClient.get") as mock_get:
            mock_get.return_value = AsyncMock(status_code=200, text=mock_html)
            mock_get.return_value.raise_for_status = lambda: None

            status = await scraper.fetch_status()
            assert status is not None
            assert status.is_holiday is True

    await scraper.close()


@pytest.mark.asyncio
async def test_frequency_parsing_new_layout(scraper):
    mock_status_html = """
    <html>
        <body>
            <a data-tab="tab-service" class="live-network-status__tab-link">
                <span aria-label="normal service"></span>
            </a>
            <div id="tab-service"></div>
            <div id="tab-interruption"></div>
        </body>
    </html>
    """
    mock_schedule_html = """
    <html>
        <body>
            <h6>Deux-Montagnes</h6>
            <span class="body-style--l-body">3 minutes 30</span>
            <h6>Anse-à-l'Orme</h6>
            <span class="body-style--l-body">7 minutes</span>
            <span class="body-style--l-body">14 minutes</span>
        </body>
    </html>
    """

    async def mock_get(url, *args, **kwargs):
        mock_resp = AsyncMock(status_code=200)
        mock_resp.raise_for_status = lambda: None
        if "horaire" in str(url) or "hours" in str(url):
            mock_resp.text = mock_schedule_html
        else:
            mock_resp.text = mock_status_html
        return mock_resp

    with patch("httpx.AsyncClient.get", side_effect=mock_get):
        status = await scraper.fetch_status()
        assert status is not None
        assert status.frequency_peak == "3 minutes 30"
        assert status.frequency_off_peak == "7 minutes"

    await scraper.close()


def test_english_schedule_url():
    settings_en = Settings(language="en")
    assert settings_en.schedule_url == "https://rem.info/en/travelling/hours-of-service"
    assert settings_en.status_url == "https://rem.info/en/travelling/network-status"


@pytest.mark.asyncio
async def test_frequency_cache_does_not_cache_none(scraper):
    mock_status_html = """
    <html>
        <body>
            <a data-tab="tab-service" class="live-network-status__tab-link">
                <span aria-label="normal service"></span>
            </a>
            <div id="tab-service"></div>
            <div id="tab-interruption"></div>
        </body>
    </html>
    """
    # Empty schedule html with no frequencies
    mock_schedule_html = "<html><body><div>No frequencies here</div></body></html>"

    async def mock_get(url, *args, **kwargs):
        mock_resp = AsyncMock(status_code=200)
        mock_resp.raise_for_status = lambda: None
        if "horaire" in str(url):
            mock_resp.text = mock_schedule_html
        else:
            mock_resp.text = mock_status_html
        return mock_resp

    with patch("httpx.AsyncClient.get", side_effect=mock_get):
        status = await scraper.fetch_status()
        assert status is not None
        assert status.frequency_peak is None
        assert status.frequency_off_peak is None

        # Verify cache was not populated with None frequency
        cache = scraper._get_cache()
        assert cache["frequency"] is None

    await scraper.close()
