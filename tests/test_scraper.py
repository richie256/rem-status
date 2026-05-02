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
