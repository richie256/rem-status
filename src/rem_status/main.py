import asyncio
import signal
from loguru import logger
from .config import Settings
from .scraper import RemScraper
from .mqtt_client import MqttClient

async def main():
    settings = Settings()
    scraper = RemScraper(settings)
    mqtt = MqttClient(settings)

    stop_event = asyncio.Event()

    def handle_signal():
        logger.info("Received termination signal")
        stop_event.set()

    # Register signals for graceful shutdown
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, handle_signal)

    logger.info("Starting REM status scraper...")
    mqtt.connect()

    try:
        while not stop_event.is_set():
            logger.debug("Fetching current status...")
            status = await scraper.fetch_status()
            is_holiday = False
            if status:
                mqtt.publish_state(status)
                is_holiday = status.is_holiday
            
            interval = settings.get_poll_interval(is_holiday)
            logger.debug(f"Sleeping for {interval} seconds...")
            try:
                # Wait for poll interval or stop signal
                await asyncio.wait_for(stop_event.wait(), timeout=interval)
            except asyncio.TimeoutError:
                # Normal case: continue loop
                pass
    except Exception as e:
        logger.error(f"Unexpected error in main loop: {e}")
    finally:
        logger.info("Stopping...")
        mqtt.disconnect()
        await scraper.close()
        logger.info("Application stopped.")

if __name__ == "__main__":
    asyncio.run(main())
