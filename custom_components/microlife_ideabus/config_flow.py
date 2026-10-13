"""Config flow for Microlife Ideabus integration bypassing explicit client pairing loops."""
import voluptuous as vol
import logging
from homeassistant import config_entries
from homeassistant.components.bluetooth import async_ble_device_from_address

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Options for multi-device compatibility
DEVICE_TYPES = {
    "blood_pressure": "Blood Pressure Monitor (B6 / WatchBP)",
    "watchbp_office": "WatchBP Office (Clinical ABPM)",
    "thermometer": "Infrared Thermometer",
    "wbo_scale": "Body Composition Scale (WBO3)"
}

class MicrolifeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Microlife Ideabus."""
    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step via graphical UI layout without triggering hardware blocks."""
        errors = {}

        if user_input is not None:
            mac_address = user_input["mac"].upper().strip()
            device_type = user_input["device_type"]
            
            _LOGGER.warning("[Microlife Flow] UI Configuration submitted for MAC: %s", mac_address)
            
            # Проверяем, видит ли ядро Home Assistant рекламу (ADV-пакеты) от прибора по воздуху
            ble_device = async_ble_device_from_address(self.hass, mac_address, connectable=True)
            
            if not ble_device:
                _LOGGER.warning("[Microlife Flow] Target device not discovered in BLE air scanning cache.")
                errors["base"] = "cannot_connect"
            else:
                # FIXED: Полностью убрали открытие сокета BleakClient.
                # Интеграция мгновенно сохраняет запись, передавая управление рабочему движку sensor.py
                _LOGGER.warning("[Microlife Flow] Device verified in BLE air cache. Registering integration entry...")
                return self.async_create_entry(
                    title=f"Microlife {mac_address}",
                    data={"mac": mac_address, "device_type": device_type}
                )

        # UI form structure using voluptuous schemas
        data_schema = vol.Schema({
            vol.Required("mac", default="EF:06:40:CE:23:8E"): str,
            vol.Required("device_type", default="blood_pressure"): vol.In(DEVICE_TYPES)
        })

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors
        )
