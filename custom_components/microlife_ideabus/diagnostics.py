"""Diagnostics support for Microlife Ideabus."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

TO_REDACT = {
    "mac",
    "address",
    "addresses",
    "serial",
    "serial_number",
    "unique_id",
    "identifiers",
    "connections",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    runtime = hass.data.get(
        DOMAIN,
        {},
    ).get(
        entry.entry_id,
        {},
    )

    diagnostics_data = {
        "entry": {
            "title": entry.title,
            "data": dict(entry.data),
            "options": dict(entry.options),
            "pref_disable_new_entities": (
                entry.pref_disable_new_entities
            ),
            "pref_disable_polling": (
                entry.pref_disable_polling
            ),
        },
        "runtime": {
            "is_connecting": runtime.get(
                "is_connecting",
            ),
            "sensor_count": len(
                runtime.get(
                    "sensors",
                    {},
                ),
            ),
            "cmd_queue_size": len(
                runtime.get(
                    "cmd_queue",
                    [],
                ),
            ),
        },
    }

    return async_redact_data(
        diagnostics_data,
        TO_REDACT,
    )
