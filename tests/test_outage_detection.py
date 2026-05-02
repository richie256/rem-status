import pytest
from unittest.mock import AsyncMock, patch
from rem_status.config import Settings
from rem_status.scraper import RemScraper


@pytest.fixture
def settings():
    return Settings(language="en", monitor_station_from="Panama", monitor_station_to="Gare Centrale")


@pytest.fixture
def scraper(settings, tmp_path):
    cache_file = tmp_path / "test_cache_outage.json"
    return RemScraper(settings, cache_file=str(cache_file))


@pytest.mark.asyncio
async def test_outage_within_range(scraper):
    mock_html = """
    <html>
        <body>
            <div class="service-status-banner">Interruption between Panama and Gare Centrale</div>
            <div class="alert-message">Technical issues at Île-des-Sœurs</div>
            <h6>3 min</h6>
            <h6>7 min</h6>
        </body>
    </html>
    """

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.return_value = AsyncMock(status_code=200, text=mock_html)
        mock_get.return_value.raise_for_status = lambda: None

        status = await scraper.fetch_status()

        assert status is not None
        assert status.is_outage is True
        assert "Île-des-Sœurs" in status.monitored_status


@pytest.mark.asyncio
async def test_outage_outside_range(scraper):
    # Range is Panama to Gare Centrale. Outage is at Brossard (outside range).
    mock_html = """
    <html>
        <body>
            <div class="service-status-banner">Interruption at Brossard</div>
            <div class="alert-message">Power failure at Brossard station</div>
            <h6>3 min</h6>
            <h6>7 min</h6>
        </body>
    </html>
    """

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.return_value = AsyncMock(status_code=200, text=mock_html)
        mock_get.return_value.raise_for_status = lambda: None

        status = await scraper.fetch_status()

        assert status is not None
        assert status.is_outage is False
        assert status.monitored_status == "Normal (Outage elsewhere)"


@pytest.mark.asyncio
async def test_network_wide_outage(scraper):
    mock_html = """
    <html>
        <body>
            <div class="service-status-banner">Network wide interruption</div>
            <h6>-</h6>
            <h6>-</h6>
        </body>
    </html>
    """

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.return_value = AsyncMock(status_code=200, text=mock_html)
        mock_get.return_value.raise_for_status = lambda: None

        status = await scraper.fetch_status()

        assert status is not None
        assert status.is_outage is True
        assert "Network wide" in status.monitored_status


@pytest.mark.asyncio
async def test_no_stations_specified(tmp_path):
    settings = Settings(monitor_station_from=None, monitor_station_to=None)
    cache_file = tmp_path / "test_cache_no_stations.json"
    scraper = RemScraper(settings, cache_file=str(cache_file))

    mock_html = """
    <html>
        <body>
            <div class="service-status-banner">Interruption at Brossard</div>
            <h6>-</h6>
            <h6>-</h6>
        </body>
    </html>
    """

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.return_value = AsyncMock(status_code=200, text=mock_html)
        mock_get.return_value.raise_for_status = lambda: None

        status = await scraper.fetch_status()

        assert status is not None
        assert status.is_outage is True
        assert "Interruption at Brossard" in status.monitored_status


@pytest.mark.asyncio
async def test_map_based_detection(scraper):
    # Panama is in range. Simulate it being out-service on the map.
    mock_html = """
    <html>
        <body>
            <div class="service-status-banner">Service - Normal</div>
            <div class="station-item">
                <div class="item-img"><span class="out-service"></span></div>
                <span class="station-name">Panama</span>
            </div>
            <h6>3 min</h6>
            <h6>7 min</h6>
        </body>
    </html>
    """

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.return_value = AsyncMock(status_code=200, text=mock_html)
        mock_get.return_value.raise_for_status = lambda: None

        status = await scraper.fetch_status()

        assert status is not None
        assert status.is_outage is True
        assert "Outage at stations: Panama" in status.monitored_status
