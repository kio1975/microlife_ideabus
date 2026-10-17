"""Config flow for Microlife Ideabus integration supporting native interactive 6-digit bonding."""
import logging
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components.bluetooth import async_ble_device_from_address

from .const import DOMAIN
from .pairing_helper import MicrolifePairingHelper

_LOGGER = logging.getLogger(__name__)

DEVICE_TYPES = {
    "blood_pressure": "Blood Pressure Monitor (B6 / WatchBP)",
    "watchbp_office": "WatchBP Office (Clinical ABPM)",
    "thermometer": "Infrared Thermometer",
    "wbo_scale": "Body Composition Scale (WBO3)"
}


class MicrolifeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Microlife Ideabus."""
    VERSION = 1

    def __init__(self):
        """Initialize the flow context store."""
        self.mac_address = None
        self.device_type = None
        self.profile1_name = None
        self.profile2_name = None
        self.helper = None

    async def async_step_user(self, user_input=None):
        """Step 1: Initialize Bluetooth pairing workflow."""
        errors = {}

        if user_input is not None:
            self.mac_address = user_input["mac"].upper().strip()
            self.device_type = user_input["device_type"]
            self.profile1_name = user_input.get(
                "profile1_name",
                "Profile 1",
            ).strip()

            self.profile2_name = user_input.get(
                "profile2_name",
                "Profile 2",
            ).strip()

            _LOGGER.info("[Microlife Flow] Step User submitted for MAC: %s", self.mac_address)
            
            ble_device = async_ble_device_from_address(self.hass, self.mac_address, connectable=True)
            if not ble_device:
                _LOGGER.warning("[Microlife Flow] Target device not discovered in BLE air scanning cache.")
                errors["base"] = "cannot_connect"
                return self._show_user_form(user_input, errors)

            # Initialize Bluetooth pairing helper
            self.helper = MicrolifePairingHelper(self.mac_address)

            # Always perform a clean bond recovery workflow.
            # This prevents stale BlueZ pairing keys from being reused
            # after integration reinstallation or failed pairing attempts.
            # Workflow:
            # remove -> pair -> PIN -> trust
            success = await self.helper.repair_pairing()
            if not success:
                errors["base"] = "cannot_connect"
                return self._show_user_form(user_input, errors)

            # Proceed to the PIN verification step
            return await self.async_step_pin()

        return self._show_user_form(user_input, errors)

    async def async_step_pin(self, user_input=None):
        """Step 2: Submit the 6-digit pairing PIN."""
        errors = {}

        if user_input is not None:
            pin_code = user_input["pin"].strip()
            
            if not pin_code.isdigit() or len(pin_code) != 6:
                errors["base"] = "invalid_pin_format"
                return self._show_pin_form(errors)

            _LOGGER.info("[Microlife Flow] Submitting 6-digit passkey to authorized BlueZ agent...")
            
            if not self.helper:
                errors["base"] = "pairing_failed"
                return self._show_pin_form(errors)

            # Submit the entered PIN to the active pairing session
            success = await self.helper.submit_pin_and_fetch_matrix(pin_code)
            
            if not success:
                errors["base"] = "pairing_failed"
                return self._show_pin_form(errors)

            # Create a unique Home Assistant config entry identifier
            await self.async_set_unique_id(self.mac_address)
            self._abort_if_unique_id_configured()

            _LOGGER.info("[Microlife Flow] Provisioning completed successfully. Creating config entry.")
            return self.async_create_entry(
            title=f"Microlife {self.mac_address}",
            data={
                "mac": self.mac_address,
                "device_type": self.device_type,
                "profile1_name": self.profile1_name,
                "profile2_name": self.profile2_name,
            },
)


        return self._show_pin_form(errors)

    def _show_user_form(self, user_input, errors):
        """Render UI voluptuous schemas input form layout."""
        default_mac = "EF:06:40:CE:23:8E"
        default_type = "blood_pressure"

        if user_input is not None:
            default_mac = user_input.get("mac", default_mac)
            default_type = user_input.get("device_type", default_type)

        data_schema = vol.Schema({
            vol.Required("mac", default=default_mac): str,
            vol.Required("device_type", default=default_type): vol.In(DEVICE_TYPES),
            vol.Required("profile1_name", default="Profile 1"): str,
            vol.Required("profile2_name", default="Profile 2"): str,
        })

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors
        )

    def _show_pin_form(self, errors):
        """Render UI voluptuous schemas input form layout."""
        return self.async_show_form(
            step_id="pin",
            data_schema=vol.Schema({
                vol.Required("pin"): str
            }),
            errors=errors
        )
