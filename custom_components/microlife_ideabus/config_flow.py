"""Config flow for Microlife Ideabus integration."""

import asyncio
import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.bluetooth import (async_ble_device_from_address, async_discovered_service_info)
from homeassistant.core import callback

from .const import DOMAIN
from .pairing_helper import MicrolifePairingHelper
from .microlife_devices import is_microlife_device

_LOGGER = logging.getLogger(__name__)

DEVICE_TYPES = {
    "blood_pressure": "Blood Pressure Monitor (B6 / WatchBP)",
    "watchbp_office": "WatchBP Office (Clinical ABPM)",
    "thermometer": "Infrared Thermometer",
    "wbo_scale": "Body Composition Scale (WBO3)",
    "oximeter": "Pulse Oximeter",
}


class MicrolifeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Microlife Ideabus."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return MicrolifeOptionsFlowHandler(config_entry)

    def __init__(self):
        """Initialize flow state."""

        self.mac_address = None
        self.device_type = None
        self.profile1_name = None
        self.profile2_name = None
        self.helper = None
        self._discovered_devices = {}

    async def async_step_user(self, user_input=None):
        """Step 1: Device selection and pairing initialization."""

        errors = {}

        if user_input is not None:

            selected_device = user_input["mac"]

            self.mac_address = (
                user_input["mac"]
                .upper()
                .strip()
            )

            self.device_type = user_input["device_type"]

            self.profile1_name = (
                user_input.get(
                    "profile1_name",
                    "Profile 1",
                ).strip()
            )

            self.profile2_name = (
                user_input.get(
                    "profile2_name",
                    "Profile 2",
                ).strip()
            )

            _LOGGER.debug(
                "[Microlife Flow] Step User submitted for MAC: %s",
                self.mac_address,
            )

            ble_device = async_ble_device_from_address(
                self.hass,
                self.mac_address,
                connectable=True,
            )

            if not ble_device:
                _LOGGER.warning(
                    "[Microlife Flow] Target device not discovered in BLE cache."
                )

                errors["base"] = "cannot_connect"

                return self._show_user_form(
                    user_input,
                    errors,
                )

            self.helper = MicrolifePairingHelper(
                self.mac_address
            )

            success = await self.helper.repair_pairing()

            if not success:
                errors["base"] = "cannot_connect"

                return self._show_user_form(
                    user_input,
                    errors,
                )

            for _ in range(50):

                if (
                    self.helper
                    and self.helper.passkey
                ):
                    break

                await asyncio.sleep(0.2)
            _LOGGER.debug(
                "PASSKEY BEFORE CONFIRM STEP = %s",
                self.helper.passkey,
            )                
            return await self.async_step_confirm()

        return self._show_user_form(
            user_input,
            errors,
        )

    async def async_step_confirm(self, user_input=None):
        """Step 2: Confirm Bluetooth passkey."""

        errors = {}

        if user_input is not None:

            if not self.helper:
                errors["base"] = "pairing_failed"

                return self._show_confirm_form(
                    errors
                )

            _LOGGER.debug(
                "[Microlife Flow] Confirming Bluetooth passkey."
            )

            success = await self.helper.confirm_pairing(
                user_input["confirm_pairing"]
            )

            if not success:
                errors["base"] = "pairing_failed"

                return self._show_confirm_form(
                    errors
                )

            await self.async_set_unique_id(
                self.mac_address
            )

            self._abort_if_unique_id_configured()

            _LOGGER.info(
                "[Microlife Flow] Provisioning completed successfully."
            )

            return self.async_create_entry(
                title=f"Microlife {self.mac_address}",
                data={
                    "mac": self.mac_address,
                    "device_type": self.device_type,
                    "profile1_name": self.profile1_name,
                    "profile2_name": self.profile2_name,
                },
            )

        return self._show_confirm_form(errors)

    def _show_user_form(
        self,
        user_input,
        errors,
    ):
        """Render initial setup form."""

        default_type = "blood_pressure"

        if user_input is not None:
            default_type = user_input.get(
                "device_type",
                default_type,
            )

        self._discovered_devices = {}

        for discovery_info in async_discovered_service_info(
            self.hass,
            False,
        ):
            name = (discovery_info.name or "").upper()

            service_uuids = {
                uuid.lower()
                for uuid in (
                    discovery_info.service_uuids or []
                )
            }

            if not is_microlife_device(
                discovery_info.name,
                service_uuids,
            ):
                continue

            address = (
                discovery_info.address
                .upper()
                .strip()
            )
            _LOGGER.debug(
                "[MICROLIFE DEVICE] name=%s address=%s",
                discovery_info.name,
                discovery_info.address,
            )
            display_name = (
                discovery_info.name
                or "Unknown BLE Device"
            )

            self._discovered_devices[address] = (
                f"{display_name} ({address})"
            )

        if self._discovered_devices:

            mac_selector = vol.In(
                self._discovered_devices
            )

        else:

            mac_selector = str

        data_schema = vol.Schema(
            {
                vol.Required(
                    "mac",
                ): mac_selector,

                vol.Required(
                    "profile1_name",
                    default="User 1 name",
                ): str,

                vol.Required(
                    "profile2_name",
                    default="User 2 name",
                ): str,

                vol.Required(
                    "device_type",
                    default=default_type,
                ): vol.In(
                    DEVICE_TYPES
                ),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )
    def _show_confirm_form(
        self,
        errors,
    ):
        """Render Bluetooth passkey confirmation form."""

        passkey = "------"

        if (
            self.helper
            and self.helper.passkey
        ):
            passkey = self.helper.passkey
        _LOGGER.debug(
            "PASSKEY IN UI FORM = %s",
            passkey,
        )
        return self.async_show_form(
            step_id="confirm",
            errors=errors,
            description_placeholders={
                "passkey": str(passkey),
            },
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "pairing_code",
                        default=passkey,
                    ): str,

                    vol.Required(
                        "confirm_pairing",
                        default=True,
                    ): bool,
                }
            ),
        )



class MicrolifeOptionsFlowHandler(
    config_entries.OptionsFlow
):
    """Microlife options flow."""

    def __init__(self, config_entry):
        self._config_entry = config_entry

    async def async_step_init(
        self,
        user_input=None,
    ):
        """Manage integration options."""

        if user_input is not None:

            return self.async_create_entry(
                title="",
                data=user_input,
            )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "profile1_name",
                        default=self._config_entry.options.get(
                            "profile1_name",
                            self._config_entry.data.get(
                                "profile1_name",
                                "Profile 1",
                            ),
                        ),
                    ): str,

                    vol.Required(
                        "profile2_name",
                        default=self._config_entry.options.get(
                            "profile2_name",
                            self._config_entry.data.get(
                                "profile2_name",
                                "Profile 2",
                            ),
                        ),
                    ): str,
                }
            ),
        )
