"""Dashboard sensor state dispatcher using isolated user matrix decoding pipelines with raw indexing."""
import logging
import os
import json
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

def load_measurement_mapping(hass):
    """Load measurement user tags."""

    mapping_file = hass.config.path(
        ".microlife_mapping.json"
    )

    if not os.path.exists(mapping_file):
        return {}

    try:
        with open(
            mapping_file,
            "r",
            encoding="utf-8",
        ) as f:
            return json.load(f)

    except Exception as err:
        _LOGGER.warning(
            "Failed to load .microlife_mapping.json: %s",
            err,
        )
    return {}

def update_bpm_user1(hass, mac, sensors, records):

    _LOGGER.debug("DEBUG sensors type=%s", type(sensors))
    _LOGGER.debug("DEBUG sensors=%r", sensors)

    if "u1" not in sensors:
        _LOGGER.debug(
            "DEBUG u1 missing. Available keys=%s",
            list(sensors.keys()) if hasattr(sensors, "keys") else "NO_KEYS"
        )
        return

    if not records:
        return
    # Filter records belonging to blood pressure before processing
    bp_records = [r for r in records if r.get("type") == "blood_pressure"]
    if not bp_records: return

    bp_records.sort(key=lambda x: x.get("time_obj"), reverse=True)
    newest = bp_records[0]
    _LOGGER.debug(
        "TIME DEBUG raw=%r tzinfo=%r iso=%s",
        newest["time_obj"],
        newest["time_obj"].tzinfo,
        newest["time_obj"].isoformat(),
    )
    ts = newest["time_obj"].isoformat()
    
    _LOGGER.info("[Microlife UI Dispatch] Committing User 1: SYS=%s, DIA=%s", newest['sys'], newest['dia'])
    sensors["u1"]["systolic"].update_state(newest["sys"], ts)
    sensors["u1"]["diastolic"].update_state(newest["dia"], ts)
    sensors["u1"]["pulse"].update_state(newest["pulse"], ts)    
    sensors["u1"]["time"].update_state(ts, ts)
    sensors["u1"]["afib"].update_state(
        newest.get("afib", False)
    )
    sensors["u1"]["ihb"].update_state(
        newest.get("ihb", False)
    )

    sensors["u1"]["arrhythmia"].update_state(
        newest.get("arrhythmia", False)
    )

    sensors["u1"]["mam"].update_state(
        bool(newest.get("mam", 0))
    )

    sensors["u1"]["cuff_ok"].update_state(
        newest.get("cuff_ok", True)
    )
   
    hist_list = [{
        "device_user": "u1",
        "datetime": r["time_str"],
        "systolic": r["sys"],
        "diastolic": r["dia"],
        "pulse": r["pulse"],
        "arrhythmia": r.get("arrhythmia", False),
        "ihb": r.get("ihb", False),
        "afib": r.get("afib", False),
        "mam": r.get("mam", 0),
        "cuff_ok": r.get("cuff_ok", True),
    } for r in bp_records]

    mapping_data = load_measurement_mapping(
        hass
    )

    for item in hist_list:

        record_key = (
            f"{mac}_{item['datetime']}"
        )

        mapping = mapping_data.get(
            record_key
        )

        if mapping:
            item["user_tag"] = (
                mapping.get(
                    "assigned_user_tag"
                )
            )
    sensors["u1"]["history"].update_history_state(len(hist_list), hist_list)


def update_bpm_user2(hass, mac, sensors, records):

    if "u2" not in sensors:
        _LOGGER.debug(
            "DEBUG u2 missing. Available keys=%s",
            list(sensors.keys()) if hasattr(sensors, "keys") else "NO_KEYS"
        )
        return

    if not records:
        return
    bp_records = [r for r in records if r.get("type") == "blood_pressure"]
    if not bp_records: return

    bp_records.sort(key=lambda x: x.get("time_obj"), reverse=True)
    newest = bp_records[0]
    _LOGGER.debug(
        "TIME DEBUG raw=%r tzinfo=%r iso=%s",
        newest["time_obj"],
        newest["time_obj"].tzinfo,
        newest["time_obj"].isoformat(),
    )
    ts = newest["time_obj"].isoformat()
    
    _LOGGER.info("[Microlife UI Dispatch] Committing User 2: SYS=%s, DIA=%s", newest['sys'], newest['dia'])
    sensors["u2"]["systolic"].update_state(newest["sys"], ts)
    sensors["u2"]["diastolic"].update_state(newest["dia"], ts)
    sensors["u2"]["pulse"].update_state(newest["pulse"], ts)
    
    
    sensors["u2"]["time"].update_state(ts, ts)
    sensors["u2"]["afib"].update_state(
        newest.get("afib", False)
    )
    sensors["u2"]["ihb"].update_state(
        newest.get("ihb", False)
    )

    sensors["u2"]["arrhythmia"].update_state(
        newest.get("arrhythmia", False)
    )

    sensors["u2"]["mam"].update_state(
        bool(newest.get("mam", 0))
    )

    sensors["u2"]["cuff_ok"].update_state(
        newest.get("cuff_ok", True)
    )

    hist_list = [{
        "device_user": "u2",
        "datetime": r["time_str"],
        "systolic": r["sys"],
        "diastolic": r["dia"],
        "pulse": r["pulse"],
        "arrhythmia": r.get("arrhythmia", False),
        "ihb": r.get("ihb", False),
        "afib": r.get("afib", False),
        "mam": r.get("mam", 0),
        "cuff_ok": r.get("cuff_ok", True),
    } for r in bp_records]
    mapping_data = load_measurement_mapping(
        hass
    )

    for item in hist_list:

        record_key = (
            f"{mac}_{item['datetime']}"
        )

        mapping = mapping_data.get(
            record_key
        )

        if mapping:
            item["user_tag"] = (
                mapping.get(
                    "assigned_user_tag"
                )
            )    
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
