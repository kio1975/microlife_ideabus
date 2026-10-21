"""Multi-device binary matrix parser for Microlife IdeaBus protocol with universal battery-drop safeguards."""
import logging
from datetime import datetime

_LOGGER = logging.getLogger(__name__)

def parse_ideabus_matrix(raw_bytes: bytearray, device_type: str = "blood_pressure") -> list:
    """Parse raw binary frames based on defragmented SDK matrix layout."""
    data = bytes(raw_bytes)
    if not data:
        return []

    records = []

    # 1. АППАРАТНЫЙ ПАРСИНГ ПУЛЬСОКСИМЕТРОВ
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

    # Строгий двухбайтовый поиск стартового маркера заголовка Ideabus
    idx = data.find(b"\x4d\x3a")
    if idx == -1 or idx + 4 > len(data):
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

    # Разбор служебных пачек ответов SDK (Мета-информация устройств)
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

    # 2. УНИВЕРСАЛЬНЫЙ АППАРАТНЫЙ ПАРСИНГ ТОНОМЕТРОВ (С КЛЮЧОМ СОРТИРОВКИ)
    if device_type in ["blood_pressure", "watchbp_office"] or reply_code in [0x31, 0x3A, 0x42, 0x51]:
        block_size = 17 if reply_code == 0x51 else (20 if payload_len % 20 == 0 else 10)
        while i + block_size <= end_pos:
            block = data[i:i+block_size]
            
            sys   = block[0]
            dia   = block[1]
            pulse = block[2]
            year  = block[3]
            month = block[4]
            day   = block[5]
            hour  = block[6]
            min_  = block[7]

            flags = block[8] if block_size >= 9 else 0

            cuff_ok = bool(flags & 0x80)
            ihb = bool(flags & 0x40)
            afib = bool(flags & 0x20)
            mam = (flags & 0x18) >> 3

            arrhythmia = ihb or afib
            
            if sys == 0 or dia == 0 or sys == 0xFF:
                i += 1
                continue

            # Универсальный предохранитель сброшенных батареек
            is_no_date = (year == 0x11 and month == 0x00 and day == 0x00)
            is_valid_date = (year >= 0 and 1 <= month <= 12 and 1 <= day <= 31 and hour <= 23 and min_ <= 59)

            if not (is_no_date or is_valid_date):
                i += 1
                continue

            if not (40 <= dia <= 130 and 70 <= sys <= 220 and 35 <= pulse <= 180):
                i += 1
                continue

            try:
                if is_no_date:
                    sort_key = datetime.min
                    dt_object = datetime(2000 + year,1,1,0,0,0,).astimezone()
                else:
                    sort_key = datetime(2000 + year, month, day, hour, min_)
                    dt_object = sort_key.astimezone()
            except ValueError:
                i += 1
                continue

            records.append({
                "type": "blood_pressure",
                "sys": sys,
                "dia": dia,
                "pulse": pulse,

                "ihb": ihb,
                "afib": afib,
                "arrhythmia": arrhythmia,

                "mam": mam,
                "cuff_ok": cuff_ok,

                "time_obj": dt_object,
                "time_str": dt_object.strftime("%Y-%m-%d %H:%M"),
                "_sort": sort_key
            })
            i += block_size

        if records:
            records.sort(key=lambda x: x["_sort"], reverse=True)
        return records

    # 3. УНИВЕРСАЛЬНЫЙ АППАРАТНЫЙ ПАРСИНГ ИНФРАКРАСНЫХ ТЕРМОМЕТРОВ (ДОБАВЛЕНА ЗАЩИТА ОТ ПУСТЫХ ДАТ)
    elif reply_code in [0x1E, 0xFE, 0xA0, 0xA1] or device_type == "thermometer":
        while i + 6 <= end_pos:
            block = data[i:i+6]
            raw_val = int.from_bytes(block[0:2], byteorder='big')
            temp = round((raw_val + 100) / 100.0, 2)
            year = int(block[2])
            month = int(block[3])
            day = int(block[4])
            hour = int(block[5])
            
            if 32.0 <= temp <= 43.5:
                # ИСПРАВЛЕНО: Защита термометров от сброса часов в 11-00-00
                is_no_date = (year == 0x11 and month == 0x00 and day == 0x00)
                is_valid_date = (year >= 0 and 1 <= month <= 12 and 1 <= day <= 31 and hour <= 23)
                
                try:
                    if is_no_date or not is_valid_date:
                        sort_key = datetime.min
                        dt_object = datetime(2000 + year,1,1,0,0,0,).astimezone()
                    else:
                        sort_key = datetime(2000 + year, month, day, hour, 0)
                        dt_object = sort_key.astimezone()
                except ValueError:
                    i += 6
                    continue

                records.append({
                    "type": "thermometer", "temperature": temp, 
                    "time_obj": dt_object, "time_str": dt_object.strftime("%Y-%m-%d %H:%M"),
                    "_sort": sort_key
                })
            i += 6
            
        if records:
            records.sort(key=lambda x: x["_sort"], reverse=True)
        return records

    # 4. УНИВЕРСАЛЬНЫЙ АППАРАТНЫЙ ПАРСИНГ ДИАГНОСТИЧЕСКИХ ВЕСОВ WBO (ДОБАВЛЕНА ЗАЩИТА ОТ ПУСТЫХ ДАТ)
    elif reply_code in [0x32, 0x41, 0x42] or device_type == "wbo_scale":
        block_size = 30 if payload_len % 30 == 0 else 14
        while i + block_size <= end_pos:
            block = data[i:i+block_size]
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
            
            # ИСПРАВЛЕНО: Защита диагностических весов от сброса часов в 11-00-00
            is_no_date = (year == 0x11 and month == 0x00 and day == 0x00)
            is_valid_date = (year >= 0 and 1 <= month <= 12 and 1 <= day <= 31 and hour <= 23 and minute <= 59)
            
            try:
                if is_no_date or not is_valid_date:
                    sort_key = datetime.min
                    dt_object = datetime(2000 + year,1,1,0,0,0,).astimezone()
                else:
                    sort_key = datetime(2000 + year, month, day, hour, minute)
                    dt_object = sort_key.astimezone()
            except ValueError:
                i += block_size
                continue
            
            record = {
                "type": "wbo_scale", "condition": condition, "weight": weight, "fat": fat, "water": water, "muscle": muscle,
                "time_obj": dt_object, "time_str": dt_object.strftime("%Y-%m-%d %H:%M"), "_sort": sort_key
            }
            if block_size == 30:
                record.update({
                    "bone": int(block[14]) / 10.0, "viscera_fat": int(block[15]) / 10.0,
                    "bmi": int.from_bytes(block[16:18], byteorder='big') / 10.0, "bmr_kcal": int.from_bytes(block[18:20], byteorder='big')
                })
            records.append(record)
            i += block_size
            
        if records:
            records.sort(key=lambda x: x["_sort"], reverse=True)
        return records

    return records
