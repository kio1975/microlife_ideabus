"""Dashboard sensor state dispatcher using isolated user matrix decoding pipelines with raw indexing."""
import logging

_LOGGER = logging.getLogger(__name__)

def update_bpm_user1(sensors, records):
    """Process and commit data for User 1 (Blood Pressure)."""
    if not records: return
    # Filter records belonging to blood pressure before processing
    bp_records = [r for r in records if r.get("type") == "blood_pressure"]
    if not bp_records: return

    bp_records.sort(key=lambda x: x.get("time_obj"), reverse=True)
    newest = bp_records[0]
    ts = newest["time_obj"].isoformat()
    
    _LOGGER.info("[Microlife UI Dispatch] Committing User 1: SYS=%s, DIA=%s", newest['sys'], newest['dia'])
    sensors["u1"]["systolic"].update_state(newest["sys"], ts)
    sensors["u1"]["diastolic"].update_state(newest["dia"], ts)
    sensors["u1"]["pulse"].update_state(newest["pulse"], ts)
    
    # ИСПРАВЛЕНО: Передаем строковый ts вместо живого объекта datetime,
    # чтобы исключить TypeError краш JSON-сериализатора в ядре HA Core.
    sensors["u1"]["time"].update_state(ts, ts)
    
    hist_list = [{
        "device_user": "u1",
        "datetime": r["time_str"], 
        "systolic": r["sys"], 
        "diastolic": r["dia"], 
        "pulse": r["pulse"],
        "arrhythmia": r.get("arrhythmia", False),
        "afib": r.get("afib", False),
        "cuff_status": r.get("cuff_status", "OK")
    } for r in bp_records]
    sensors["u1"]["history"].update_history_state(len(hist_list), hist_list)


def update_bpm_user2(sensors, records):
    """Process and commit data for User 2 (Blood Pressure)."""
    if not records: return
    bp_records = [r for r in records if r.get("type") == "blood_pressure"]
    if not bp_records: return

    bp_records.sort(key=lambda x: x.get("time_obj"), reverse=True)
    newest = bp_records[0]
    ts = newest["time_obj"].isoformat()
    
    _LOGGER.info("[Microlife UI Dispatch] Committing User 2: SYS=%s, DIA=%s", newest['sys'], newest['dia'])
    sensors["u2"]["systolic"].update_state(newest["sys"], ts)
    sensors["u2"]["diastolic"].update_state(newest["dia"], ts)
    sensors["u2"]["pulse"].update_state(newest["pulse"], ts)
    
    # ИСПРАВЛЕНО: Фикс типизации времени для Пользователя 2
    sensors["u2"]["time"].update_state(ts, ts)
    
    hist_list = [{
        "device_user": "u2",
        "datetime": r["time_str"], 
        "systolic": r["sys"], 
        "diastolic": r["dia"], 
        "pulse": r["pulse"],
        "arrhythmia": r.get("arrhythmia", False),
        "afib": r.get("afib", False),
        "cuff_status": r.get("cuff_status", "OK")
    } for r in bp_records]
    sensors["u2"]["history"].update_history_state(len(hist_list), hist_list)


def update_thermo_sensors(user_sensors, records):
    """Adaptive parser block for Infrared Thermometers."""
    if not records: return
    temp_records = [r for r in records if r.get("type") == "thermometer"]
    if not temp_records: return

    temp_records.sort(key=lambda x: x.get("time_obj"), reverse=True)
    newest = temp_records[0]
    ts = newest["time_obj"].isoformat()
    
    _LOGGER.info("[Microlife UI Dispatch] Committing Thermometer: TEMP=%s", newest['temperature'])
    user_sensors["temperature"].update_state(newest['temperature'], ts)


def update_oximeter_sensors(user_sensors, records):
    """Adaptive real-time aggregator for Pulse Oximeters."""
    if not records: return
    oxy_records = [r for r in records if r.get("type") == "oximeter"]
    if not oxy_records: return

    oxy_records.sort(key=lambda x: x.get("time_obj"), reverse=True)
    newest = oxy_records[0]
    ts = newest["time_obj"].isoformat()
    
    _LOGGER.info("[Microlife UI Dispatch] Committing Oximeter: SpO2=%s, Pulse=%s", newest['spo2'], newest['pulse'])
    user_sensors["spo2"].update_state(newest["spo2"], ts)
    user_sensors["pulse"].update_state(newest["pulse"], ts)
    user_sensors["pi"].update_state(newest["perf_index"], ts)


def update_scale_sensors(user_sensors, records):
    """Adaptive matrix parser for Body Composition WBO Scales."""
    if not records: return
    scale_records = [r for r in records if r.get("type") == "wbo_scale"]
    if not scale_records: return

    scale_records.sort(key=lambda x: x.get("time_obj"), reverse=True)
    newest = scale_records[0]
    ts = newest["time_obj"].isoformat()
    
    _LOGGER.info("[Microlife UI Dispatch] Committing Scales: Weight=%s", newest['weight'])
    user_sensors["weight"].update_state(newest["weight"], ts)
    user_sensors["fat"].update_state(newest["fat"], ts)
    user_sensors["water"].update_state(newest["water"], ts)
    user_sensors["muscle"].update_state(newest["muscle"], ts)
    
    hist_list = [{
        "datetime": r["time_str"], 
        "weight": r["weight"], 
        "fat": r["fat"], 
        "water": r["water"],
        "muscle": r["muscle"],
        "bone": r.get("bone"),
        "viscera_fat": r.get("viscera_fat"),
        "bmi": r.get("bmi"),
        "bmr_kcal": r.get("bmr_kcal")
    } for r in scale_records]
    user_sensors["history"].update_history_state(len(hist_list), hist_list)
