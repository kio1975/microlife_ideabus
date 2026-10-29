"""Initial setup supervisor engine for Microlife Ideabus integration."""

import asyncio
import logging
import time
from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import (
    async_register_advertisement_callback,
    BluetoothServiceInfoBleak,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, PLATFORMS
from .services import register_microlife_services
from .sensor_worker import connect_and_fetch_worker
from .frontend import async_register_panel
from dataclasses import dataclass, field

@dataclass
class MicrolifeRuntimeData:
    sensors: dict = field(default_factory=dict)
    cmd_queue: list = field(default_factory=list)
    is_connecting: bool = False
    device_meta: dict = field(default_factory=dict)
    ble_error_stats: dict = field(default_factory=dict)
    device_info_sensors: dict = field(default_factory=dict)
    
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    """Set up integration when Config Entry is loaded."""

    _LOGGER.info(
        "Initializing Microlife Ideabus integration for device: %s",
        entry.title,
    )
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    current_context = MicrolifeRuntimeData()

    entry.runtime_data = current_context

    if not hass.data[DOMAIN].get("services_registered"):
        register_microlife_services(
            hass,
            current_context.sensors,
        )
        hass.data[DOMAIN]["services_registered"] = True

    mac_address = entry.data["mac"].upper().strip()
    device_type = entry.data["device_type"]
    
    def _bluetooth_advertisement_callback(
        service_info: BluetoothServiceInfoBleak,
    ) -> None:
        """Process Bluetooth advertisement from the target device."""

        advertisement_address = (
            service_info.address or ""
        ).upper().strip()
        #("adv_counter", 0)
        #current_context["adv_counter"] += 1
        #_LOGGER.debug("[CALLBACK ENTRY] ""counter=%s ""addr=%s ""name=%s ""rssi=%s ""source=%s ""connectable=%s",current_context["adv_counter"],advertisement_address,getattr(service_info,"name", None),getattr(service_info, "rssi",None),getattr(service_info,"source", None),getattr(service_info, "connectable", None),)

        try:
            _LOGGER.debug(
                "[SERVICE INFO DUMP] %s",
                vars(service_info),
            )
        except Exception as ex:
            _LOGGER.debug(
                "[SERVICE INFO DUMP FAILED] %s",
                ex,
            )        
        now = time.monotonic()

        _LOGGER.debug(
            "[ADV DEBUG] addr=%s raw=%r adv_time=%s now=%s delta=%s ",
            advertisement_address,
            getattr(service_info, "raw", None),
            getattr(service_info, "time", None),
            now,
            (
                now - service_info.time
                if getattr(service_info, "time", None)
                else "NO_TIME"
            ),
        )
        # Callback is registered without an external address filter.
        # All non-target devices are filtered out here.
        if advertisement_address != mac_address:
            _LOGGER.debug(
                "[NON TARGET ADV] addr=%s target=%s",
                advertisement_address,
                mac_address,
            )
            return
        _LOGGER.debug(
            "[TARGET DEVICE MATCH] %s",
            advertisement_address,
        )
        _LOGGER.debug(
            "[B6 FULL] addr=%s name=%s rssi=%s manufacturer=%s service_data=%s ",
            advertisement_address,
            getattr(service_info, "name", None),
            getattr(service_info, "rssi", None),
            getattr(service_info, "manufacturer_data", None),
            getattr(service_info, "service_data", None),
        )
        age = (
            now - service_info.time
            if getattr(service_info, "time", None)
            else 999
        )

        if age > 1:
            _LOGGER.debug(
                "[STALE ADV] addr=%s age=%.3f",
                advertisement_address,
                age,
            )
            return

        _LOGGER.debug(
            "[B6 AGE] %.3f seconds",
            age,
        )

        _LOGGER.debug(
            "[ADV DEBUG] addr=%s rssi=%s raw=%r "
            "time=%s delta=%.3f",
            advertisement_address,
            getattr(service_info, "rssi", None),
            getattr(service_info, "raw", None),
            getattr(service_info, "time", None),
            age,
        )

        _LOGGER.debug(
            "[RAW_ADV] B6 addr=%s name=%s rssi=%s "
            "is_connecting=%s",
            advertisement_address,
            getattr(service_info, "name", None),
            getattr(service_info, "rssi", None),
            current_context.is_connecting,
        )
        _LOGGER.debug(
            "[CONNECT LOCK BEFORE] %s",
            current_context.is_connecting,
        )
        # Current BLE session or cooldown period is still active.
        # The flag is cleared in sensor_worker.py after 20 seconds.
        if current_context.is_connecting:
            _LOGGER.debug(
                "[DISCOVERY] B6 ADV ignored because "
                "is_connecting=True"
            )
            return

        _LOGGER.info(
            "[DISCOVERY] STARTING WORKER for B6 %s",
            advertisement_address,
        )

        # Set connection lock before starting the task.
        # This prevents multiple workers from running simultaneously.
        current_context.is_connecting = True
        _LOGGER.debug(
            "[CONNECT LOCK SET TRUE] ts=%s",
            time.monotonic(),
        )
        def spawn_isolated_task() -> None:
            """Launch worker in a separate asynchronous task."""
            _LOGGER.debug(
                "[SPAWN TASK] addr=%s",
                advertisement_address,
            )
            _LOGGER.debug(
                "[DISCOVERY] SPAWNING WORKER TASK"
            )
            _LOGGER.debug(
                "[WORKER START REQUEST] "
                "addr=%s "
                "rssi=%s",
                advertisement_address,
                getattr(service_info, "rssi", None),
            )
            asyncio.create_task(
                connect_and_fetch_worker(
                    hass,
                    entry,
                    current_context.sensors,
                    mac_address,
                    device_type,
                    service_info,
                    current_context,
                )
            )

        hass.loop.call_soon_threadsafe(
            spawn_isolated_task
        )

    # Allow BlueZ to close L2CAP channels
    # left over from Config Flow and pairing.
    await asyncio.sleep(5.0)

    await hass.config_entries.async_forward_entry_setups(
        entry,
        PLATFORMS,
    )
    current_context.is_connecting = True

    asyncio.create_task(
        connect_and_fetch_worker(
            hass,
            entry,
            current_context.sensors,
            mac_address,
            device_type,
            None,
            current_context,
        )
    )
    entry.async_on_unload(
        bluetooth.async_register_advertisement_callback(
            hass,
            _bluetooth_advertisement_callback,
            mac_address,
        )
    )
    _LOGGER.debug(
        "[CALLBACK REGISTERED] target=%s time=%s "
        "unfiltered callback with internal MAC guard; target=%s ",
        mac_address,
        time.monotonic(),
        mac_address,
    )

    await async_register_panel(hass)
    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    """Unload integration."""

    _LOGGER.info(
        "Unloading Microlife Ideabus integration"
    )

    unload_ok = await hass.config_entries.async_unload_platforms(
        entry,
        PLATFORMS,
    )

    if unload_ok:
        for service in [
            "tag_measurement",
            "export_history",
            "sync_time",
            "clear_history",
            "repair_bluetooth",
        ]:
            if hass.services.has_service(
                DOMAIN,
                service,
            ):
                hass.services.async_remove(
                    DOMAIN,
                    service,
                )

        hass.data.get(DOMAIN, {}).pop(
            entry.entry_id,
            None,
        )

    return unload_ok
