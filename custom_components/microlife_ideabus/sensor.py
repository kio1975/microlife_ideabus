"""Sensor platform for Microlife Ideabus integration."""
import logging
from datetime import datetime
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.entity import EntityCategory

from .const import DOMAIN
from .device import get_microlife_device_info

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> bool:
    """Set up the Microlife sensor platform."""
    mac_address = entry.data.get("mac").upper().strip()
    device_type = entry.data.get("device_type")
    
    _LOGGER.info("[Microlife Core] Initializing sensor platform for MAC: %s", mac_address)
    
    entry_context = entry.runtime_data
    if not entry_context:
        _LOGGER.error("[Microlife Core] Integration context missing from hass.data during sensor setup!")
        return False
    device_meta = entry_context.device_meta

    # Device association is now performed exclusively through the Bluetooth identifier.
    device_info = get_microlife_device_info(
        mac_address,
        device_type,
    )

    device_meta = entry_context.device_meta

    manufacturer_sensor = MicrolifeDeviceInfoSensor(
        mac_address,
        "manufacturer",
        "Manufacturer",
        device_info,
        device_meta,
    )

    model_sensor = MicrolifeDeviceInfoSensor(
        mac_address,
        "model",
        "Model",
        device_info,
        device_meta,
    )

    serial_sensor = MicrolifeDeviceInfoSensor(
        mac_address,
        "serial",
        "Serial Number",
        device_info,
        device_meta,
    )

    firmware_sensor = MicrolifeDeviceInfoSensor(
        mac_address,
        "firmware",
        "Firmware Version",
        device_info,
        device_meta,
    )

    hardware_sensor = MicrolifeDeviceInfoSensor(
        mac_address,
        "hardware",
        "Hardware Revision",
        device_info,
        device_meta,
    )

    software_sensor = MicrolifeDeviceInfoSensor(
        mac_address,
        "software",
        "Software Revision",
        device_info,
        device_meta,
    )

    rssi_sensor = MicrolifeDeviceInfoSensor(
        mac_address,
        "rssi",
        "RSSI",
        device_info,
        device_meta,
    )
    
    entities = []
  
    sensors_map = {"u1": {}, "u2": {}}
    
    sensors_map["device_info"] = {
        "rssi": rssi_sensor,
        "manufacturer": manufacturer_sensor,
        "model": model_sensor,
        "serial": serial_sensor,
        "firmware": firmware_sensor,
        "hardware": hardware_sensor,
        "software": software_sensor,
    }
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
        afib_sensor = MicrolifeFlagSensor(mac_address, f"{user}_afib", f"{user_label} AFIB", device_info)
        ihb_sensor = MicrolifeFlagSensor(mac_address, f"{user}_ihb", f"{user_label} IHB", device_info)
        arrhythmia_sensor = MicrolifeFlagSensor(mac_address, f"{user}_arrhythmia", f"{user_label} Arrhythmia", device_info)
        mam_sensor = MicrolifeFlagSensor(mac_address, f"{user}_mam", f"{user_label} MAM", device_info)
        cuff_ok_sensor = MicrolifeFlagSensor(mac_address, f"{user}_cuff_ok", f"{user_label} Cuff OK", device_info)


        entities.extend([systolic, diastolic, pulse, time_sensor, history_sensor, afib_sensor, ihb_sensor, arrhythmia_sensor, mam_sensor, cuff_ok_sensor])

        

        # Mapping used by ui_dispatch.py update handlers
        sensors_map[user]["systolic"] = systolic
        sensors_map[user]["diastolic"] = diastolic
        sensors_map[user]["pulse"] = pulse
        sensors_map[user]["time"] = time_sensor
        sensors_map[user]["history"] = history_sensor
        sensors_map[user]["afib"] = afib_sensor
        sensors_map[user]["ihb"] = ihb_sensor
        sensors_map[user]["arrhythmia"] = arrhythmia_sensor
        sensors_map[user]["mam"] = mam_sensor
        sensors_map[user]["cuff_ok"] = cuff_ok_sensor



        

    # Publish the sensor map to the integration runtime context for use by the background worker
    entry_context.sensors.clear()
    entry_context.sensors.update(sensors_map)
    entry_context.device_info_sensors = {
        "rssi": rssi_sensor,
        "manufacturer": manufacturer_sensor,
        "model": model_sensor,
        "serial": serial_sensor,
        "firmware": firmware_sensor,
        "hardware": hardware_sensor,
        "software": software_sensor,
    }
    entities.extend(
        [
            rssi_sensor,
            manufacturer_sensor,
            model_sensor,
            serial_sensor,
            firmware_sensor,
            hardware_sensor,
            software_sensor,
        ]
    )
    # Register entities with Home Assistant Core
    async_add_entities(entities)
    _LOGGER.info("[Microlife Core] Full 26-sensor pipeline integrated into HA Core successfully.")
    return True


class MicrolifeBpmSensor(RestoreEntity, SensorEntity):
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
        
    async def async_added_to_hass(self):
        """Restore previous state."""
        await super().async_added_to_hass()

        if (state := await self.async_get_last_state()) is None:
            return
        if state.state in ("unknown", "unavailable", None):
            return
        try:
            self._attr_native_value = int(float(state.state))
        except (ValueError, TypeError):
            self._attr_native_value = state.state

        self._attr_extra_state_attributes.update(
            state.attributes
        )
        
    def update_state(self, value, ts=None):
        """Update the current sensor value."""
        self._attr_native_value = value
        if ts:
            self._attr_extra_state_attributes["device_measurement_timestamp"] = ts
        self.async_write_ha_state()


class MicrolifeTimestampSensor(RestoreEntity, SensorEntity):
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

    async def async_added_to_hass(self):
        """Restore previous state."""
        await super().async_added_to_hass()

        if (state := await self.async_get_last_state()) is None:
            return
        if state.state in ("unknown", "unavailable", None):
            return
        try:
            self._attr_native_value = datetime.fromisoformat(
                state.state
            )
        except ValueError:
            pass

        self._attr_extra_state_attributes.update(
            state.attributes
        )
        
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


class MicrolifeHistorySensor(RestoreEntity, SensorEntity):
    """History archive sensor used to store the complete measurement matrix."""

    def __init__(self, mac, unique_suffix, name, device_info):
        """Initialize the history matrix collector."""
        self._mac = mac
        self._attr_unique_id = f"microlife_{mac}_{unique_suffix}"
        self._attr_name = name
        self._attr_native_unit_of_measurement = "records"
        self._attr_device_info = device_info
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_native_value = 0
        self._attr_extra_state_attributes = {"records": []}

    async def async_added_to_hass(self):
        """Restore previous state."""
        await super().async_added_to_hass()

        if (state := await self.async_get_last_state()) is None:
            return
        if state.state in ("unknown", "unavailable", None):
            return

        records = state.attributes.get("records",[])

        self._attr_native_value = len(records)

        self._attr_extra_state_attributes["records"] = records
        
    def update_history_state(self, count, history_list):
        """Commit measurement history received from ui_dispatch.py."""
        self._attr_native_value = count
        self._attr_extra_state_attributes["records"] = history_list
        self.async_write_ha_state()

class MicrolifeFlagSensor(
    RestoreEntity,
    SensorEntity,
):
    def __init__(
        self,
        mac,
        unique_suffix,
        name,
        device_info,
    ):
        self._attr_unique_id = (
            f"microlife_{mac}_{unique_suffix}"
        )
        self._attr_name = name
        self._attr_device_info = device_info
        self._attr_native_value = False

    async def async_added_to_hass(self):
        await super().async_added_to_hass()

        if (state := await self.async_get_last_state()) is None:
            return
        if state.state in ("unknown", "unavailable", None):
            return
        self._attr_native_value = (
            str(state.state).lower()
            in ("true", "on", "1")
        )

    def update_state(self, value):
        self._attr_native_value = bool(value)
        self.async_write_ha_state()

class MicrolifeDeviceInfoSensor(
    RestoreEntity,
    SensorEntity,
):
    """BLE device information sensor."""

    def __init__(
        self,
        mac,
        key,
        name,
        device_info,
        device_meta,
    ):
        self._key = key
        self._device_meta = device_meta

        self._attr_unique_id = (
            f"microlife_{mac}_{key}"
        )

        self._attr_name = name
        self._attr_device_info = device_info
        if key == "rssi":
            self._attr_native_unit_of_measurement = "dBm"    
        self._attr_entity_category = (
            EntityCategory.DIAGNOSTIC
        )
    async def async_added_to_hass(self):
        await super().async_added_to_hass()

        if (state := await self.async_get_last_state()) is None:
            return

        if state.state in ("unknown", "unavailable", None):
            return

        self._device_meta[self._key] = state.state
        
    @property
    def native_value(self):
        return self._device_meta.get(
            self._key
        )

    def refresh(self):
        self.async_write_ha_state()
