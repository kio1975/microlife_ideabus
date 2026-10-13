"""Dashboard sensor state dispatcher using isolated user matrix decoding pipelines with raw indexing."""
import logging
from datetime import datetime

_LOGGER = logging.getLogger(__name__)

def parse_ideabus_matrix(raw_bytes) -> list:
    """Your gold-standard matrix parser sliding by 1 byte window frame on pattern mismatch."""
    data = bytes(raw_bytes)
    idx = data.find(b"\x4d\x3a")
    if idx == -1:
        return []

    start_pos = idx + 4
    payload_len = int.from_bytes(data[idx+2:idx+4], byteorder='big')
    end_pos = start_pos + payload_len
    if end_pos > len(data):
        end_pos = len(data)

    records = []
    i = start_pos
    while i + 10 <= end_pos:
        block = data[i:i+10]
        
        # Mapped to single-byte integer slices to prevent formatting crashes
        sys, dia, pulse, year, month, day, hour, min_ = block[0], block[1], block[2], block[3], block[4], block[5], block[6], block[7]

        if sys == 0 or dia == 0 or sys == 0xFF:
            i += 1
            continue

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
                dt_object = datetime.now().astimezone()
                sort_key = datetime.min
            else:
                sort_key = datetime(2000 + year, month, day, hour, min_)
                dt_object = sort_key.astimezone()
        except ValueError:
            i += 1
            continue

        records.append({
            "sys": sys, "dia": dia, "pulse": pulse,
            "time_obj": dt_object, "time_str": dt_object.strftime("%Y-%m-%d %H:%M"),
            "_sort": sort_key
        })
        i += 10
    return records


def update_bpm_user1(sensors, data_u1):
    """Process and commit data for User 1."""
    records = parse_ideabus_matrix(data_u1)
    if not records: return
    records.sort(key=lambda x: x["_sort"], reverse=True)
    newest = records[0]
    ts = newest["time_obj"].isoformat()
    
    _LOGGER.info(f"[Microlife UI Dispatch] Committing User 1: SYS={newest['sys']}, DIA={newest['dia']}")
    sensors["u1"]["systolic"].update_state(newest["sys"], ts)
    sensors["u1"]["diastolic"].update_state(newest["dia"], ts)
    sensors["u1"]["pulse"].update_state(newest["pulse"], ts)
    sensors["u1"]["time"].update_state(newest["time_obj"], ts)
    
    hist_list = [{"datetime": r["time_str"], "systolic": r["sys"], "diastolic": r["dia"], "pulse": r["pulse"]} for r in records]
    sensors["u1"]["history"].update_history_state(len(hist_list), hist_list)


def update_bpm_user2(sensors, data_u2):
    """Process and commit data for User 2."""
    records = parse_ideabus_matrix(data_u2)
    if not records: return
    records.sort(key=lambda x: x["_sort"], reverse=True)
    newest = records[0]
    ts = newest["time_obj"].isoformat()
    
    _LOGGER.info(f"[Microlife UI Dispatch] Committing User 2: SYS={newest['sys']}, DIA=%d", newest["sys"], newest["dia"])
    sensors["u2"]["systolic"].update_state(newest["sys"], ts)
    sensors["u2"]["diastolic"].update_state(newest["dia"], ts)
    sensors["u2"]["pulse"].update_state(newest["pulse"], ts)
    sensors["u2"]["time"].update_state(newest["time_obj"], ts)
    
    hist_list = [{"datetime": r["time_str"], "systolic": r["sys"], "diastolic": r["dia"], "pulse": r["pulse"]} for r in records]
    sensors["u2"]["history"].update_history_state(len(hist_list), hist_list)


# --- MULTI-DEVICE EXTENSION PARSERS MAPPED FROM SDK ---
def update_thermo_sensors(user_sensors, raw_bytes):
    """Adaptive parser block for Infrared Thermometers."""
    data = bytes(raw_bytes)
    idx = data.find(b"\x4d\x2e") # T: header signature
    if idx == -1: return
    # Thermometer processing layout maps here...

def update_oximeter_sensors(user_sensors, raw_bytes):
    """Adaptive real-time aggregator for Pulse Oximeters."""
    data = bytes(raw_bytes)
    # Oximeter processing layout maps here...

def update_scale_sensors(user_sensors, raw_bytes):
    """Adaptive matrix parser for Body Composition WBO Scales."""
    data = bytes(raw_bytes)
    # Scale processing layout maps here...
