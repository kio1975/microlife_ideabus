"""Генерация информации об устройствах Microlife для Home Assistant."""
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH
from .const import DOMAIN


def get_microlife_device_info(mac: str, device_type: str = "blood_pressure") -> DeviceInfo:
    """Генерация DeviceInfo для любого типа медицинского прибора Microlife."""
    # Приводим MAC к верхнему регистру для сквозной синхронизации с BLE-стеком HA
    clean_mac = mac.strip().upper()
    
    # Полный справочник моделей на основе анализа декомпилированных Java-классов
    device_models = {
        "blood_pressure": ("Тонометр Microlife B6 Connect", "B6 Connect"),
        "watchbp_office": ("Тонометр Microlife WatchBP Office", "WatchBP Office AFIB"),
        "wbo_scale": ("Диагностические весы Microlife WBO", "WS 200 BT"),
        "thermometer": ("Термометр Microlife NC Connect", "NC 150 BT"),
        "oximeter": ("Пульсоксиметр Microlife OXY Connect", "OXY 200 BT")
    }
    
    # Получаем название и модель, либо ставим дефолт, если тип неизвестен
    device_name, model_name = device_models.get(
        device_type, 
        ("Устройство Microlife", "Generic IdeaBus")
    )
    
    return DeviceInfo(
        identifiers={(DOMAIN, clean_mac)},
        name=device_name,
        manufacturer="Microlife",
        model=model_name,
        connections={(CONNECTION_BLUETOOTH, clean_mac)}
    )
