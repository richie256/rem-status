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

    refresh_event = asyncio.Event()
    mqtt.on_refresh_requested = lambda: loop.call_soon_threadsafe(refresh_event.set)

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

            refresh_event.clear()

            # Wait for poll interval, stop signal, or refresh request
            wait_tasks = [
                asyncio.create_task(stop_event.wait()),
                asyncio.create_task(refresh_event.wait()),
            ]
            try:
                await asyncio.wait(
                    wait_tasks,
                    timeout=interval,
                    return_when=asyncio.FIRST_COMPLETED,
                )
            finally:
                for task in wait_tasks:
                    if not task.done():
                        task.cancel()
    except Exception as e:
        logger.error(f"Unexpected error in main loop: {e}")
    finally:
        logger.info("Stopping...")
        mqtt.disconnect()
        await scraper.close()
        logger.info("Application stopped.")


if __name__ == "__main__":
    asyncio.run(main())
