"""Интеграция Microlife Ideabus для Home Assistant Core."""
import logging
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN
from .services import register_microlife_services

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Настройка интеграции при активации Config Entry."""
    _LOGGER.info("Инициализация интеграции Microlife Ideabus для устройства: %s", entry.title)
    
    # Выделяем изолированное современное хранилище для датчиков в этой сессии
    entry.runtime_data = {
        "sensors": {}
    }

    # Регистрируем службы и передаем им ссылку на контекст датчиков
    register_microlife_services(hass, entry.runtime_data["sensors"])

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Удаление или перезапуск интеграции."""
    _LOGGER.info("Выгрузка интеграции Microlife Ideabus")
    
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        # ИСПРАВЛЕНО: Корректно и полностью очищаем ВСЕ четыре службы из ядра HA
        if hass.services.has_service(DOMAIN, "tag_measurement"):
            hass.services.async_remove(DOMAIN, "tag_measurement")
        if hass.services.has_service(DOMAIN, "export_history"):
            hass.services.async_remove(DOMAIN, "export_history")
        if hass.services.has_service(DOMAIN, "sync_time"):
            hass.services.async_remove(DOMAIN, "sync_time")
        if hass.services.has_service(DOMAIN, "clear_history"):
            hass.services.async_remove(DOMAIN, "clear_history")
            
    return unload_ok
