"""Generate Microlife device information for Home Assistant."""
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH
from .const import DOMAIN


def get_microlife_device_info(mac: str, device_type: str = "blood_pressure") -> DeviceInfo:
    """Generate DeviceInfo for supported Microlife medical devices."""
    # Normalize MAC address for consistent BLE identification.
    clean_mac = mac.strip().upper()
    
    # Device model mapping derived from protocol analysis.
    device_models = {
        "blood_pressure": ("Microlife B6 Connect Blood Pressure Monitor", "B6 Connect"),
        "watchbp_office": ("Microlife WatchBP Office Blood Pressure Monitor", "WatchBP Office AFIB"),
        "wbo_scale": ("Microlife WBO Diagnostic Scale", "WS 200 BT"),
        "thermometer": ("Microlife NC Connect Thermometer", "NC 150 BT"),
        "oximeter": ("Microlife OXY Connect Pulse Oximeter", "OXY 200 BT")
    }
    
    # Resolve device name and model or use generic fallback.
    device_name, model_name = device_models.get(
        device_type, 
        ("Microlife Device", "Generic IdeaBus")
    )
    
    return DeviceInfo(
        identifiers={(DOMAIN, clean_mac)},
        name=device_name,
        manufacturer="Microlife",
        model=model_name,
        connections={(CONNECTION_BLUETOOTH, clean_mac)}
    )
