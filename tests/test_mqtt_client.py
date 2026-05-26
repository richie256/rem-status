"""Tests for MqttClient discovery and state publishing.

The sample alert text below is the real payload from the May 26, 2026
Brossard–Panama incident (636 chars) that exposed the HA 255-char state limit bug.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from rem_status.config import Settings
from rem_status.models import RemStatus
from rem_status.mqtt_client import MqttClient

# ---------------------------------------------------------------------------
# Real-world sample data — May 26 2026, Brossard–Panama slowdown
# ---------------------------------------------------------------------------
# The scraper joined two alert elements with " | ".  The result is 636 chars,
# well over HA's 255-char entity-state limit, causing sensor.rem_status_scraper_rem_alert
# to fall back to "unknown" on every update.
BROSSARD_PANAMA_ALERT_636 = (
    "StationsBrossardPanamaDétails :Ralentissement de service entre Brossard et Panama "
    "dans toutes les directions. Problème de matériel roulant."
    "Une navette REM circule sur voie unique entre les stations Brossard et Panama. "
    "Veuillez vous référer aux agents en station pour obtenir de l'assistance et "
    "prêter attention aux annonces sonores. | Ralentissement de service entre Brossard "
    "et Panama dans toutes les directions. Problème de matériel roulant."
    "Une navette REM circule sur voie unique entre les stations Brossard et Panama. "
    "Veuillez vous référer aux agents en station pour obtenir de l'assistance et "
    "prêter attention aux annonces sonores."
)

# Earlier that day: interruption with restoration time (311 chars)
BROSSARD_PANAMA_INTERRUPTION_311 = (
    "StationsBrossardPanamaDétails :Interruption de service entre Brossard et Panama "
    "dans toutes les directions. Problème de matériel roulant."
    "rétablissement prévu :16 h 33Alternatives de déplacement :Voir les détails | "
    "Interruption de service entre Brossard et Panama dans toutes les directions. "
    "Problème de matériel roulant."
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def settings():
    return Settings(
        mqtt_host="localhost",
        mqtt_port=1883,
        mqtt_base_topic="home/transit/rem",
        mqtt_discovery_prefix="homeassistant",
    )


@pytest.fixture
def mqtt_client(settings):
    with patch("paho.mqtt.client.Client"):
        client = MqttClient(settings)
        client.client = MagicMock()
        return client


def _published_payloads(mqtt_client) -> dict[str, dict]:
    """Return {topic: parsed_payload} for every publish() call."""
    result = {}
    for c in mqtt_client.client.publish.call_args_list:
        topic, payload, *_ = c.args
        try:
            result[topic] = json.loads(payload)
        except (json.JSONDecodeError, TypeError):
            result[topic] = payload
    return result


# ---------------------------------------------------------------------------
# _publish_discovery
# ---------------------------------------------------------------------------

class TestPublishDiscovery:
    def test_status_sensor_has_json_attributes_topic(self, mqtt_client):
        """Status sensor discovery payload must include json_attributes_topic.

        This is the fix for the 255-char bug: by pointing json_attributes_topic
        at the same state topic, HA stores the full JSON (including the long
        'alert' field) as entity attributes with no length restriction.
        """
        mqtt_client._publish_discovery()
        payloads = _published_payloads(mqtt_client)

        status_cfg = payloads["homeassistant/sensor/rem_status/status/config"]
        assert "json_attributes_topic" in status_cfg
        assert status_cfg["json_attributes_topic"] == "home/transit/rem/state"

    def test_status_sensor_state_topic_and_value_template_unchanged(self, mqtt_client):
        """Adding attributes must not break the existing state_topic / value_template."""
        mqtt_client._publish_discovery()
        payloads = _published_payloads(mqtt_client)

        status_cfg = payloads["homeassistant/sensor/rem_status/status/config"]
        assert status_cfg["state_topic"] == "home/transit/rem/state"
        assert status_cfg["value_template"] == "{{ value_json.status }}"

    def test_other_sensors_do_not_have_json_attributes_topic(self, mqtt_client):
        """Only the status sensor gets attributes; others stay state-only."""
        mqtt_client._publish_discovery()
        payloads = _published_payloads(mqtt_client)

        for sensor_id in ("alert", "frequency_peak", "frequency_off_peak", "monitored_status"):
            topic = f"homeassistant/sensor/rem_status/{sensor_id}/config"
            assert "json_attributes_topic" not in payloads[topic], (
                f"sensor '{sensor_id}' should not expose json_attributes_topic"
            )

    def test_all_expected_sensors_are_published(self, mqtt_client):
        """Regression guard: discovery must still publish all sensors."""
        mqtt_client._publish_discovery()
        payloads = _published_payloads(mqtt_client)

        expected_topics = [
            "homeassistant/sensor/rem_status/status/config",
            "homeassistant/sensor/rem_status/frequency_peak/config",
            "homeassistant/sensor/rem_status/frequency_off_peak/config",
            "homeassistant/sensor/rem_status/alert/config",
            "homeassistant/sensor/rem_status/monitored_status/config",
            "homeassistant/binary_sensor/rem_status/is_outage/config",
        ]
        for topic in expected_topics:
            assert topic in payloads, f"missing discovery for {topic}"


# ---------------------------------------------------------------------------
# publish_state — May 26 incident scenarios
# ---------------------------------------------------------------------------

class TestPublishState:
    def test_long_alert_published_in_full(self, mqtt_client):
        """Reproduce the May 26 slowdown: 636-char alert must not be truncated.

        Before the fix the alert sensor fell back to 'unknown' because HA
        rejected states longer than 255 chars.  The JSON payload itself has no
        such limit, so the full text must survive the round-trip.
        """
        assert len(BROSSARD_PANAMA_ALERT_636) > 255

        status = RemStatus(
            status="Ralentissement de service",
            alert=BROSSARD_PANAMA_ALERT_636,
            frequency_peak="10 min",
            frequency_off_peak="20 min",
            monitored_status="Ralentissement entre Brossard et Panama",
            is_outage=True,
            direction="Entre Brossard et Bois-Franc",
            language="fr",
        )

        mqtt_client.publish_state(status)

        mqtt_client.client.publish.assert_called_once()
        topic, payload = mqtt_client.client.publish.call_args.args
        assert topic == "home/transit/rem/state"

        data = json.loads(payload)
        assert data["alert"] == BROSSARD_PANAMA_ALERT_636
        assert len(data["alert"]) > 255

    def test_interruption_with_restoration_time(self, mqtt_client):
        """Earlier May 26 event: interruption payload at 311 chars also exceeded the limit."""
        assert len(BROSSARD_PANAMA_INTERRUPTION_311) > 255

        status = RemStatus(
            status="Interruption de service",
            alert=BROSSARD_PANAMA_INTERRUPTION_311,
            is_outage=True,
            direction="Entre Brossard et Bois-Franc",
            language="fr",
        )

        mqtt_client.publish_state(status)

        _, payload = mqtt_client.client.publish.call_args.args
        data = json.loads(payload)
        assert data["alert"] == BROSSARD_PANAMA_INTERRUPTION_311
        assert data["status"] == "Interruption de service"
        assert data["is_outage"] is True

    def test_normal_service_alert_is_null(self, mqtt_client):
        """During normal service the alert field must be null (not '') so that
        HA attribute-change triggers don't fire spuriously."""
        status = RemStatus(
            status="Service Normal",
            alert=None,
            frequency_peak="3 min 30 s",
            frequency_off_peak="7 min",
            is_outage=False,
            direction="Entre Brossard et Bois-Franc",
            language="fr",
        )

        mqtt_client.publish_state(status)

        _, payload = mqtt_client.client.publish.call_args.args
        data = json.loads(payload)
        assert data["alert"] is None
        assert data["is_outage"] is False
