# GEMINI.md - REM Status MQTT Scraper

This document provides foundational mandates and architectural context for Gemini CLI when working on this project.

## Architectural Principles

- **Asynchronous First**: All network I/O (scraping, MQTT) must remain asynchronous using `asyncio`, `httpx`, and async-friendly patterns for `paho-mqtt`.
- **Configuration over Hardcoding**: Use `pydantic-settings` in `config.py` for all operational parameters. Never hardcode URLs or selectors that might change.
- **Home Assistant Compatibility**: Maintain the MQTT Discovery protocol. Any new sensors or binary sensors added must follow the Home Assistant discovery schema in `mqtt_client.py`.
- **Robust Scraping**: The REM website structure is subject to change. Always verify selectors in `scraper.py` against the latest HTML structure if scraping fails.

## Key Components

- `src/rem_status/scraper.py`: Contains the logic for parsing `rem.info`. Use CSS selectors for extraction.
- `src/rem_status/mqtt_client.py`: Manages the MQTT lifecycle and discovery payloads.
- `src/rem_status/models.py`: The single source of truth for the data schema.

## Development Standards

- **Type Hinting**: Mandatory for all functions and classes.
- **Logging**: Use `loguru` for all application logging. Avoid `print()` statements.
- **Testing**: New features or scraper logic changes must be accompanied by mock-based tests in `tests/`.
- **Dependencies**: Manage dependencies via `pyproject.toml`.

## Common Tasks

- **Adding a New Sensor**:
  1. Update `RemStatus` model in `models.py`.
  2. Update `_parse_*` methods in `scraper.py`.
  3. Add the sensor configuration to `_publish_discovery()` in `mqtt_client.py`.
- **Updating Selectors**:
  - If the REM website changes its layout, update the CSS selectors in `RemScraper._parse_status`, `_parse_frequencies`, and `_parse_alert`.
