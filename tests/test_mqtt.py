import json
from unittest.mock import MagicMock

from rem_status.config import Settings
from rem_status.models import RemStatus
from rem_status.mqtt_client import MqttClient


def test_mqtt_init_sets_lwt():
    settings = Settings()
    mqtt = MqttClient(settings)

    # Verify availability topic and will_set
    assert mqtt.availability_topic == f"{settings.mqtt_base_topic}/availability"


def test_mqtt_on_connect_publishes_availability_and_discovery():
    settings = Settings()
    mqtt = MqttClient(settings)
    mqtt.client.publish = MagicMock()
    mqtt.client.subscribe = MagicMock()

    mqtt._on_connect(mqtt.client, None, None, 0)

    # Verify online availability was published with retain=True
    mqtt.client.publish.assert_any_call(
        mqtt.availability_topic,
        payload="online",
        qos=1,
        retain=True,
    )

    # Verify HA status subscription
    mqtt.client.subscribe.assert_called_with(f"{settings.mqtt_discovery_prefix}/status")

    # Verify discovery payload includes availability_topic
    discovery_calls = [call for call in mqtt.client.publish.call_args_list if "/config" in str(call)]
    assert len(discovery_calls) > 0
    for call in discovery_calls:
        payload = json.loads(call[0][1])
        assert payload["availability_topic"] == mqtt.availability_topic
        assert call[1]["retain"] is True


def test_mqtt_publish_state_retained():
    settings = Settings()
    mqtt = MqttClient(settings)
    mqtt.client.publish = MagicMock()

    status = RemStatus(
        status="Normal",
        frequency_peak="3 min",
        frequency_off_peak="7 min",
        alert=None,
        monitored_status="Normal",
        is_outage=False,
        direction=settings.direction,
        language=settings.language,
        is_holiday=False,
    )

    mqtt.publish_state(status)

    topic = f"{settings.mqtt_base_topic}/state"
    mqtt.client.publish.assert_called_once_with(topic, status.model_dump_json(), retain=True)


def test_mqtt_disconnect_publishes_offline():
    settings = Settings()
    mqtt = MqttClient(settings)
    mqtt.client.publish = MagicMock()
    mqtt.client.loop_stop = MagicMock()
    mqtt.client.disconnect = MagicMock()

    mqtt.disconnect()

    mqtt.client.publish.assert_called_once_with(
        mqtt.availability_topic,
        payload="offline",
        qos=1,
        retain=True,
    )
    mqtt.client.loop_stop.assert_called_once()
    mqtt.client.disconnect.assert_called_once()


def test_mqtt_refresh_requested_on_ha_birth():
    settings = Settings()
    mqtt = MqttClient(settings)
    mock_refresh = MagicMock()
    mqtt.on_refresh_requested = mock_refresh

    msg = MagicMock()
    msg.topic = f"{settings.mqtt_discovery_prefix}/status"
    msg.payload = b"online"

    mqtt._on_message(mqtt.client, None, msg)
    mock_refresh.assert_called_once()
