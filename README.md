# REM Status MQTT Scraper

This Python project scrapes the official REM Montreal website for service status, frequencies, and alerts, then publishes the data to an MQTT broker. It supports Home Assistant MQTT Discovery for easy integration.

## Features
- **Async Scraper:** High-performance asynchronous fetching using `httpx`.
- **MQTT Integration:** Reliable publication of service status to MQTT.
- **Home Assistant Discovery:** Automatically appears as sensors in Home Assistant.
- **Configurable:** Easily customize direction, language, and MQTT settings.

## Installation

1.  **Clone the repository.**
2.  **Create a virtual environment:**
    ```bash
    python -m venv venv
    source venv/bin/activate
    ```
3.  **Install dependencies:**
    ```bash
    pip install .
    ```
    Alternatively, if you want to install from source for development:
    ```bash
    pip install -e .
    ```

## Configuration

Copy the `.env.example` file to `.env` and fill in your details:
```bash
cp .env.example .env
```

| Variable | Description | Default |
| :--- | :--- | :--- |
| `MQTT_HOST` | MQTT Broker address | `localhost` |
| `MQTT_PORT` | MQTT Broker port | `1883` |
| `DIRECTION` | Target REM direction | `Entre Brossard et Bois-Franc` |
| `LANGUAGE` | Language (`fr` or `en`) | `fr` |
| `POLL_INTERVAL` | Seconds between updates | `300` |

## Usage

Run the scraper:
```bash
rem-status-mqtt
```
Or run as a module:
```bash
python -m src.rem_status.main
```

## Data Scraped
- **Service Status:** (e.g., "Normal", "Interruption")
- **Frequency Peak:** Train frequency during peak hours.
- **Frequency Off-Peak:** Train frequency during off-peak hours.
- **Alerts:** Specific alert messages if present.

## Testing
Run the tests using `pytest`:
```bash
pip install pytest pytest-asyncio
pytest
```
