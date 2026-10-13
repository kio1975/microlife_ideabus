"""Constants and complete multi-device command factory for Microlife IdeaBus / eBelter protocol."""

DOMAIN = "microlife_ideabus"

# --- IdeaBus (BPM / Thermometers / Scales) GATT Characteristic UUIDs ---
NOTIFY_UUID = "0000fff1-0000-1000-8000-00805f9b34fb"
WRITE_UUID  = "0000fff2-0000-1000-8000-00805f9b34fb"

# --- Standard Bluetooth SIG UUIDs from SDK ---
UUID_FIRMWARE = "00002a28-0000-1000-8000-00805f9b34fb"
UUID_BATTERY  = "00002a19-0000-1000-8000-00805f9b34fb"

# --- Pulse Oximeter (Oxygen) UUIDs from OxygenProtocol.smali ---
OXYGEN_SERVICE_UUID = "cdeacb80-5235-4c07-8846-93a37ee6b86d"
OXYGEN_NOTIFY_UUID  = "cdeacb81-5235-4c07-8846-93a37ee6b86d"
OXYGEN_WRITE_UUID   = "cdeacb82-5235-4c07-8846-93a37ee6b86d"

# Device Routing Transmission Codes from Smali decompilation
DEVICE_BPM_SEND = 0xFF
DEVICE_SCALE_SEND = 0x41
DEVICE_THERMO_SEND = 0xFE
DEVICE_WBO_OFFICE = 0x42  # WatchBP Office from WBOProtocol.smali


def calc_checksum_1byte(payload: bytearray) -> int:
    """Standard 1-byte CRC mapped from calcChecksum method in smali for IdeaBus models."""
    return sum(payload) & 0xFF


def calc_checksum_2byte(payload: bytearray) -> int:
    """Extended 16-bit CRC mapped from calcChecksum4 method in smali for WatchBP Clinical ABPM."""
    return sum(payload) & 0xFFFF


def build_microlife_command(device_type: str, user_index: int) -> bytes:
    """Universal control frame generator mapped from dynamic 12-byte buildCmdString smali methods."""
    if device_type == "oximeter":
        return b""
        
    if device_type == "watchbp_office":
        # Professional ABPM Device Spec (Uses dynamic 2-byte CRC4)
        packet = bytearray([0x4D, DEVICE_WBO_OFFICE, 0x00, 0x0A, 0x05, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, user_index])
        crc = calc_checksum_2byte(packet)
        packet.append((crc >> 8) & 0xFF)
        packet.append(crc & 0xFF)
        return bytes(packet)

    # Standard 12-byte IdeaBus structural layout for BPM, Scales, and Thermometers
    if device_type == "wbo_scale":
        device_id = DEVICE_SCALE_SEND
    elif device_type == "thermometer":
        device_id = DEVICE_THERMO_SEND
    else:
        device_id = DEVICE_BPM_SEND

    # [Header, DeviceID, LenHigh, LenLow, 7 bytes of padding zeros, UserIndex]
    packet = bytearray([0x4D, device_id, 0x00, 0x09, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, user_index])
    packet.append(calc_checksum_1byte(packet))
    return bytes(packet)
