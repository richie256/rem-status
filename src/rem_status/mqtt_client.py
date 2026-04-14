import json
import paho.mqtt.client as mqtt
from loguru import logger
from .config import Settings
from .models import RemStatus


class MqttClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
        if settings.mqtt_username and settings.mqtt_password:
            self.client.username_pw_set(settings.mqtt_username, settings.mqtt_password)

        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            logger.info("Connected to MQTT broker")
            self._publish_discovery()
        else:
            logger.error(f"Failed to connect to MQTT broker with code {rc}")

    def _on_disconnect(self, client, userdata, rc, properties=None, reason_code=None):
        logger.warning(f"Disconnected from MQTT broker with code {rc}")

    def connect(self):
        try:
            self.client.connect(self.settings.mqtt_host, self.settings.mqtt_port, 60)
            self.client.loop_start()
        except Exception as e:
            logger.error(f"Error connecting to MQTT: {e}")

    def _publish_discovery(self):
        prefix = self.settings.mqtt_discovery_prefix
        base_topic = self.settings.mqtt_base_topic
        device = {
            "identifiers": ["rem_status_scraper"],
            "name": "REM Status Scraper",
            "model": "REM Status",
            "manufacturer": "Gemini CLI Scraper",
        }

        sensors = [
            {"name": "Status", "id": "status", "icon": "mdi:train"},
            {"name": "Frequency Peak", "id": "frequency_peak", "icon": "mdi:clock-fast"},
            {"name": "Frequency Off-Peak", "id": "frequency_off_peak", "icon": "mdi:clock-slow"},
            {"name": "Alert", "id": "alert", "icon": "mdi:alert-circle"},
        ]

        for sensor in sensors:
            discovery_topic = f"{prefix}/sensor/{base_topic}/{sensor['id']}/config"
            payload = {
                "name": f"REM {sensor['name']}",
                "state_topic": f"{base_topic}/state",
                "value_template": f"{{{{ value_json.{sensor['id']} }}}}",
                "unique_id": f"rem_{sensor['id']}",
                "device": device,
                "icon": sensor["icon"],
            }
            self.client.publish(discovery_topic, json.dumps(payload), retain=True)
            logger.debug(f"Published discovery for {sensor['name']}")

    def publish_state(self, status: RemStatus):
        topic = f"{self.settings.mqtt_base_topic}/state"
        payload = status.model_dump_json()
        self.client.publish(topic, payload)
        logger.info(f"Published state: {payload}")

    def disconnect(self):
        self.client.loop_stop()
        self.client.disconnect()
