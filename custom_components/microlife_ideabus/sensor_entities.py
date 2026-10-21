"""Sensor entity definitions for the Microlife Ideabus integration."""
import copy
import logging
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.helpers.device_registry import DeviceInfo

from .device import get_microlife_device_info

_LOGGER = logging.getLogger(__name__)

class MicrolifeSensor(SensorEntity):
    """Syntactically valid representation of a Microlife sensor entity."""
    
    def __init__(self, entry, key, name, unit, mac, device_class_str=None, device_type="blood_pressure"):
        self._entry = entry
        self._key = key
        self._name = name
        self._unit = unit
        self._device_type = device_type
        self._state = None
        self._attrs = {}
        self._mac = str(mac).upper()

        # Secure mapping of strings to HA core SensorDeviceClass enums
        self._attr_device_class = None
        if device_class_str == "weight":
            self._attr_device_class = SensorDeviceClass.WEIGHT
        elif device_class_str == "temperature":
            self._attr_device_class = SensorDeviceClass.TEMPERATURE
        elif device_class_str == "timestamp":
            self._attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def name(self): 
        return f"Microlife {self._name}"
        
    @property
    def unique_id(self): 
        return f"microlife_ideabus_{self._entry.entry_id}_{self._key}"
        
    @property
    def state(self): 
        return self._state
        
    @property
    def extra_state_attributes(self): 
        return self._attrs
        
    @property
    def unit_of_measurement(self): 
        return self._unit

    @property
    def device_info(self) -> DeviceInfo:
        return get_microlife_device_info(self._mac, self._device_type)

    def update_state(self, value, timestamp_str):
        """Thread-safe state update triggered by the background download worker."""
        self._state = value
        self._attrs = {"measurement_time": timestamp_str}
        
        if self.hass:
            # ИСПРАВЛЕНО: Безопасный вызов обновления состояния из фонового воркера в основной поток HA
            _LOGGER.debug("[Microlife Entity] Dispatching state update to Core UI loop for %s: %s", self._key, value)
            self.hass.loop.call_soon_threadsafe(self.async_write_ha_state)

    def update_history_state(self, count, history_data):
        """Thread-safe full memory matrix archive state update."""
        self._state = count
        self._attrs = {"measurements": copy.deepcopy(history_data)}
        
        if self.hass:
            # ИСПРАВЛЕНО: Потокобезопасный пуш архива измерений
            _LOGGER.debug("[Microlife Entity] Dispatching history package to Core UI loop for archive: %s", self._key)
            self.hass.loop.call_soon_threadsafe(self.async_write_ha_state)
