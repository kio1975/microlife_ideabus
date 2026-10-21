"""Initial setup supervisor engine for Microlife Ideabus integration."""

import asyncio
import logging

from homeassistant.components.bluetooth import (
    async_register_callback,
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, PLATFORMS
from .services import register_microlife_services
from .sensor_worker import connect_and_fetch_worker

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    """Настройка интеграции при активации Config Entry."""

    _LOGGER.info(
        "Инициализация интеграции Microlife Ideabus для устройства: %s",
        entry.title,
    )

    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    hass.data[DOMAIN][entry.entry_id] = {
        "sensors": {},
        "cmd_queue": [],
        "is_connecting": False,
    }

    current_context = hass.data[DOMAIN][entry.entry_id]

    register_microlife_services(
        hass,
        current_context["sensors"],
    )

    mac_address = entry.data["mac"].upper().strip()
    device_type = entry.data["device_type"]

    def _bluetooth_advertisement_callback(
        service_info: BluetoothServiceInfoBleak,
        change,
    ) -> None:
        """Обработать Bluetooth advertisement целевого устройства."""

        advertisement_address = (
            service_info.address or ""
        ).upper().strip()

        # Callback зарегистрирован без внешнего адресного фильтра.
        # Все чужие устройства немедленно отсекаются здесь.
        if advertisement_address != mac_address:
            return

        _LOGGER.error(
            "[RAW_ADV] B6 addr=%s name=%s rssi=%s "
            "change=%s is_connecting=%s",
            advertisement_address,
            getattr(service_info, "name", None),
            getattr(service_info, "rssi", None),
            change,
            current_context.get("is_connecting", False),
        )

        # Текущая BLE-сессия или cooldown ещё не завершены.
        # Флаг сбрасывается в sensor_worker.py через 20 секунд.
        if current_context.get("is_connecting", False):
            _LOGGER.error(
                "[DISCOVERY] B6 ADV ignored because "
                "is_connecting=True"
            )
            return

        _LOGGER.error(
            "[DISCOVERY] STARTING WORKER for B6 %s",
            advertisement_address,
        )

        _LOGGER.info(
            "[Microlife Callback] Target device %s detected "
            "in air. Status change: %s. "
            "Launching isolated task...",
            mac_address,
            change,
        )

        # Устанавливаем блокировку до запуска задачи.
        # Это защищает от запуска нескольких worker одновременно.
        current_context["is_connecting"] = True

        def spawn_isolated_task() -> None:
            """Запустить worker в отдельной асинхронной задаче."""

            _LOGGER.error(
                "[DISCOVERY] SPAWNING WORKER TASK"
            )

            asyncio.create_task(
                connect_and_fetch_worker(
                    hass,
                    entry,
                    current_context["sensors"],
                    mac_address,
                    device_type,
                    service_info,
                    current_context,
                )
            )

        hass.loop.call_soon_threadsafe(
            spawn_isolated_task
        )

    # Даём BlueZ закрыть L2CAP-каналы,
    # оставшиеся после Config Flow и сопряжения.
    await asyncio.sleep(15.0)

    await hass.config_entries.async_forward_entry_setups(
        entry,
        PLATFORMS,
    )

    entry.async_on_unload(
        async_register_callback(
            hass,
            _bluetooth_advertisement_callback,

            # Намеренно без фильтра Home Assistant.
            # Проверка MAC выполняется внутри callback.
            {},

            BluetoothScanningMode.PASSIVE,
        )
    )

    _LOGGER.error(
        "[CALLBACK REGISTERED] "
        "unfiltered callback with internal MAC guard; target=%s",
        mac_address,
    )
    
    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    """Выгрузить или перезапустить интеграцию."""

    _LOGGER.info(
        "Выгрузка интеграции Microlife Ideabus"
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
