"""Constants and complete multi-device command factory for Microlife IdeaBus / eBelter protocol."""
from homeassistant.const import Platform

DOMAIN = "microlife_ideabus"
PLATFORMS = [Platform.SENSOR]

# --- IdeaBus (BPM / Thermometers / Scales) GATT Characteristic UUIDs ---
NOTIFY_UUID = "0000fff1-0000-1000-8000-00805f9b34fb"
WRITE_UUID  = "0000fff2-0000-1000-8000-00805f9b34fb"

# --- Device Information Characteristic UUIDs ---
CHAR_MANUFACTURER = "00002a29-0000-1000-8000-00805f9b34fb"
CHAR_MODEL        = "00002a24-0000-1000-8000-00805f9b34fb"
CHAR_SERIAL       = "00002a25-0000-1000-8000-00805f9b34fb"
UUID_FIRMWARE     = "00002a28-0000-1000-8000-00805f9b34fb"
UUID_BATTERY      = "00002a19-0000-1000-8000-00805f9b34fb"

# --- Pulse Oximeter (Oxygen) UUIDs ---
OXYGEN_SERVICE_UUID = "cdeacb80-5235-4c07-8846-93a37ee6b86d"
OXYGEN_NOTIFY_UUID  = "cdeacb81-5235-4c07-8846-93a37ee6b86d"
OXYGEN_WRITE_UUID   = "cdeacb82-5235-4c07-8846-93a37ee6b86d"

# Device Routing Transmission Codes
DEVICE_BPM_SEND = 0xFF
DEVICE_SCALE_SEND = 0x41
DEVICE_THERMO_SEND = 0xFE
DEVICE_WBO_OFFICE = 0x42

def calc_checksum_1byte(payload: bytearray) -> int:
    """Calculate 8-bit IdeaBus checksum."""
    return sum(payload) & 0xFF

def calc_checksum_2byte(payload: bytearray) -> int:
    """Calculate 16-bit IdeaBus checksum."""
    return sum(payload) & 0xFFFF

def build_microlife_command(device_type: str, user_index: int) -> bytes:
    """Build IdeaBus command packet for supported Microlife devices."""
    if device_type == "oximeter":
        return b""
    if device_type == "watchbp_office":
        packet = bytearray([0x4D, DEVICE_WBO_OFFICE, 0x00, 0x0A, 0x05, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, user_index])
        crc = calc_checksum_2byte(packet)
        packet.append((crc >> 8) & 0xFF)
        packet.append(crc & 0xFF)
        return bytes(packet)

    if device_type == "wbo_scale":
        device_id = DEVICE_SCALE_SEND
    elif device_type == "thermometer":
        device_id = DEVICE_THERMO_SEND
    else:
        device_id = DEVICE_BPM_SEND

    packet = bytearray([0x4D, device_id, 0x00, 0x09, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, user_index])
    packet.append(calc_checksum_1byte(packet))
    return bytes(packet)
