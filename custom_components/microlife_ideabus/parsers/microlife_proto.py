"""Multi-device binary matrix parser for Microlife IdeaBus protocol."""
import logging
from datetime import datetime

_LOGGER = logging.getLogger(__name__)

def parse_ideabus_matrix(raw_bytes: bytearray, device_type: str = "blood_pressure") -> list:
    """Parse raw binary frames based on defragmented SDK matrix."""
    data = bytes(raw_bytes)
    if not data:
        return []

    records = []

    if device_type == "oximeter":
        i = 0
        while i + 4 <= len(data):
            if int(data[i]) == 0x81:
                pulse = int(data[i+1]) & 0xFF
                spo2 = int(data[i+2]) & 0xFF
                pi = int(data[i+3]) & 0xFF
                if 30 <= spo2 <= 100 and 30 <= pulse <= 240:
                    records.append({
                        "type": "oximeter", "spo2": spo2, "pulse": pulse, "perf_index": pi / 10.0,
                        "time_obj": datetime.now().astimezone(), "time_str": datetime.now().strftime("%Y-%m-%d %H:%M")
                    })
                i += 4
            else:
                i += 1
        return records

    idx = data.find(b"\x4d")
    if idx == -1 or idx + 4 > len(data):
        return []

    reply_code = data[idx + 1]
    payload_len = int.from_bytes(data[idx+2:idx+4], byteorder='big')
    start_pos = idx + 4
    end_pos = start_pos + payload_len
    
    if end_pos > len(data):
        end_pos = len(data)

    i = start_pos

    if reply_code in [0x05, 0x0B, 0x0C, 0x0F]:
        block = data[start_pos:end_pos]
        if len(block) >= 6:
            max_user = int(block[0])
            max_mem = int(block[1])
            hardware_flags = int(block[2])
            interval = int(block[3])
            measure_times = int.from_bytes(block[4:6], byteorder='big')
            sn_str = "Unknown"
            if len(block) > 10:
                try:
                    sn_str = block[6:16].decode("utf-8").strip()
                except Exception:
                    sn_str = block[6:16].hex().upper()

            return [{
                "type": "device_info", "max_users": max_user, "max_memory_slots": max_mem,
                "hardware_afib_support": bool(hardware_flags & 0x02), "hardware_ihb_support": bool(hardware_flags & 0x01),
                "abpm_interval_min": interval, "total_measurements_count": measure_times, "serial_number": sn_str
            }]

    if reply_code in [0x31, 0x3A, 0x42, 0x51]:
        block_size = 17 if reply_code == 0x51 else (20 if payload_len % 20 == 0 else 10)
        while i + block_size <= end_pos:
            block = data[i:i+block_size]
            
            systole = int(block[0])
            dia     = int(block[1])
            hr      = int(block[2])
            year    = int(block[3])
            month   = int(block[4])
            day     = int(block[5])
            hour    = int(block[6])
            minute  = int(block[7])
            status  = int(block[8])
            mam_byte = int(block[9])

            if systole == 0 or dia == 0 or systole == 0xFF:
                i += 1
                continue

            # Теперь извлечение флагов работает строго с числами int, исключая ошибку типов
            cuff_ok = (status & 0x80) >> 7
            has_ihb = bool((status & 0x40) >> 6)
            has_afib = bool((status & 0x20) >> 5)
            has_pad = bool((status & 0x10) >> 4)
            is_am, is_pm, is_nocturnal = bool(status & 0x04), bool(status & 0x02), bool(status & 0x01)

            try:
                dt_object = datetime(2000 + year, month, day, hour, minute).astimezone()
            except ValueError:
                dt_object = datetime.now().astimezone()

            tag_profile = "Clinical ABPM" if reply_code == 0x42 else "Standard"
            if is_nocturnal:
                tag_profile = "Night (Auto)"
            elif is_am:
                tag_profile = "Morning"
            elif is_pm:
                tag_profile = "Evening"

            records.append({
                "type": "blood_pressure", "sys": systole, "dia": dia, "pulse": hr,
                "arrhythmia": has_ihb or has_afib, "afib": has_afib, "pad_index": has_pad,
                "cuff_status": "OK" if cuff_ok == 0 else "Error/Movement",
                "profile_mode": tag_profile, "time_obj": dt_object, "time_str": dt_object.strftime("%Y-%m-%d %H:%M")
            })
            i += block_size

    elif reply_code in [0x1E, 0xFE, 0xA0, 0xA1]:
        while i + 6 <= end_pos:
            block = data[i:i+6]
            raw_val = int.from_bytes(block[0:2], byteorder='big')
            temp = round((raw_val + 100) / 100.0, 2)
            year = int(block[2])
            month = int(block[3])
            day = int(block[4])
            hour = int(block[5])
            
            if 32.0 <= temp <= 43.5:
                try:
                    dt_object = datetime(2000 + year, month, day, hour, 0).astimezone()
                except ValueError:
                    dt_object = datetime.now().astimezone()
                records.append({
                    "type": "thermometer", "temperature": temp, "time_obj": dt_object, "time_str": dt_object.strftime("%Y-%m-%d %H:%M")
                })
            i += 6

    elif reply_code in [0x32, 0x41, 0x42]:
        block_size = 30 if payload_len % 30 == 0 else 14
        while i + block_size <= end_pos:
            block = data[i:i+14]
            condition = int(block[0])
            raw_weight = int.from_bytes(block[1:3], byteorder='big')
            weight = raw_weight / 10.0 if raw_weight < 3000 else raw_weight / 100.0
            fat = int.from_bytes(block[3:5], byteorder='big') / 10.0
            water = int.from_bytes(block[5:7], byteorder='big') / 10.0
            muscle = int.from_bytes(block[7:9], byteorder='big') / 10.0
            
            year = int(block[9])
            month = int(block[10])
            day = int(block[11])
            hour = int(block[12])
            minute = int(block[13])
            
            record = {
                "type": "wbo_scale", "condition": condition, "weight": weight, "fat": fat, "water": water, "muscle": muscle,
                "time_obj": datetime.now().astimezone(), "time_str": datetime.now().strftime("%Y-%m-%d %H:%M")
            }
            if block_size == 30:
                record.update({
                    "bone": int(data[i+14]) / 10.0, "viscera_fat": int(data[i+15]) / 10.0,
                    "bmi": int.from_bytes(data[i+16:i+18], byteorder='big') / 10.0, "bmr_kcal": int.from_bytes(data[i+18:i+20], byteorder='big')
                })
            records.append(record)
            i += block_size

    return records
