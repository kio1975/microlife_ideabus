"""Sensor platform for Microlife Ideabus integration."""
import logging
from datetime import datetime
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN
from .device import get_microlife_device_info

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> bool:
    """Set up the Microlife sensor platform."""
    mac_address = entry.data.get("mac").upper().strip()
    device_type = entry.data.get("device_type")
    
    _LOGGER.info("[Microlife Core] Initializing sensor platform for MAC: %s", mac_address)
    
    entry_context = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if not entry_context:
        _LOGGER.error("[Microlife Core] Integration context missing from hass.data during sensor setup!")
        return False

    # Device association is now performed exclusively through the Bluetooth identifier.
    device_info = get_microlife_device_info(
        mac_address,
        device_type,
    )
    entities = []
    sensors_map = {"u1": {}, "u2": {}}

    profile1_name = entry.options.get(
        "profile1_name",
        entry.data.get("profile1_name", "Profile 1"),
    )

    profile2_name = entry.options.get(
        "profile2_name",
        entry.data.get("profile2_name", "Profile 2"),
    )

    for user in ["u1", "u2"]:
        user_label = (
            profile1_name
            if user == "u1"
            else profile2_name
        )
        
        # Pass "blood_pressure" as a string to avoid compatibility issues
        # with legacy Home Assistant enum implementations.
        systolic = MicrolifeBpmSensor(mac_address, f"{user}_systolic", f"{user_label} Systolic", "mmHg", "blood_pressure", device_info)
        diastolic = MicrolifeBpmSensor(mac_address, f"{user}_diastolic", f"{user_label} Diastolic", "mmHg", "blood_pressure", device_info)
        pulse = MicrolifeBpmSensor(mac_address, f"{user}_pulse", f"{user_label} Pulse", "bpm", None, device_info)
        
        # Last measurement timestamp sensor (strict TIMESTAMP device class)
        time_sensor = MicrolifeTimestampSensor(mac_address, f"{user}_time", f"{user_label} Measurement Time", device_info)
        
        # History matrix sensor
        history_sensor = MicrolifeHistorySensor(mac_address, f"{user}_history", f"{user_label} History Matrix", device_info)
        
        entities.extend([systolic, diastolic, pulse, time_sensor, history_sensor])
        
        # Mapping used by ui_dispatch.py update handlers
        sensors_map[user]["systolic"] = systolic
        sensors_map[user]["diastolic"] = diastolic
        sensors_map[user]["pulse"] = pulse
        sensors_map[user]["time"] = time_sensor
        sensors_map[user]["history"] = history_sensor

    # Publish the sensor map to the integration runtime context for use by the background worker
    entry_context["sensors"].clear()
    entry_context["sensors"].update(sensors_map)

    # Register entities with Home Assistant Core
    async_add_entities(entities)
    _LOGGER.info("[Microlife Core] Full 10-sensor pipeline integrated into HA Core successfully.")
    return True


class MicrolifeBpmSensor(SensorEntity):
    """Representation of Microlife numeric sensors (blood pressure and pulse)."""

    def __init__(self, mac, unique_suffix, name, unit, device_class, device_info):
        """Initialize the sensor."""
        self._mac = mac
        self._attr_unique_id = f"microlife_{mac}_{unique_suffix}"
        self._attr_name = name
        self._attr_native_unit_of_measurement = unit
        self._attr_device_info = device_info
        self._attr_state_class = SensorStateClass.MEASUREMENT
        
        if device_class:
            self._attr_device_class = device_class
            
        self._attr_native_value = None
        self._attr_extra_state_attributes = {}

    def update_state(self, value, ts=None):
        """Update the current sensor value."""
        self._attr_native_value = value
        if ts:
            self._attr_extra_state_attributes["device_measurement_timestamp"] = ts
        self.async_write_ha_state()


class MicrolifeTimestampSensor(SensorEntity):
    """Dedicated Home Assistant timestamp sensor."""

    def __init__(self, mac, unique_suffix, name, device_info):
        """Initialize the timestamp sensor."""
        self._mac = mac
        self._attr_unique_id = f"microlife_{mac}_{unique_suffix}"
        self._attr_name = name
        self._attr_device_info = device_info
        self._attr_device_class = SensorDeviceClass.TIMESTAMP
        self._attr_native_unit_of_measurement = None
        self._attr_native_value = None
        self._attr_extra_state_attributes = {}

    def update_state(self, value, ts=None):
        """Update date/time state. Expects a datetime object."""
        if isinstance(value, datetime):
            self._attr_native_value = value
        elif isinstance(value, str):
            try:
                self._attr_native_value = datetime.fromisoformat(value)
            except ValueError:
                _LOGGER.error("[Microlife Core] Received invalid string format for timestamp: %s", value)
                return
        else:
            self._attr_native_value = value

        if ts:
            self._attr_extra_state_attributes["device_measurement_timestamp"] = ts
        self.async_write_ha_state()


class MicrolifeHistorySensor(SensorEntity):
    """History archive sensor used to store the complete measurement matrix."""

    def __init__(self, mac, unique_suffix, name, device_info):
        """Initialize the history matrix collector."""
        self._mac = mac
        self._attr_unique_id = f"microlife_{mac}_{unique_suffix}"
        self._attr_name = name
        self._attr_native_unit_of_measurement = "records"
        self._attr_device_info = device_info
        self._attr_native_value = 0
        self._attr_extra_state_attributes = {"records": []}

    def update_history_state(self, count, history_list):
        """Commit measurement history received from ui_dispatch.py."""
        self._attr_native_value = count
        self._attr_extra_state_attributes["records"] = history_list
        self.async_write_ha_state()
