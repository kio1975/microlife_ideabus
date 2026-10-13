"""User services module for Microlife Ideabus integration."""
import os
import csv
import json
import copy
import logging
from datetime import datetime
import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN, WRITE_UUID, calc_checksum_1byte

_LOGGER = logging.getLogger(__name__)

SERVICE_CLEAR_SCHEMA = vol.Schema({
    vol.Required("mac"): cv.string,
    vol.Optional("user_key", default="u1"): vol.In(["u1", "u2"]),
})


def register_microlife_services(hass: HomeAssistant, sensors: dict):
    """Register custom services for handling medical archives."""

    async def handle_tag_measurement(call):
        """Assign an identity tag to a specific measurement record."""
        mac = call.data.get("mac").upper()
        user_key = call.data.get("user_key")
        target_time = call.data.get("datetime")
        new_tag = call.data.get("user_tag", "unknown")
        
        mapping_file = hass.config.path(".microlife_mapping.json")
        
        def update_mapping_sync():
            mapping_data = {}
            if os.path.exists(mapping_file):
                try:
                    with open(mapping_file, "r", encoding="utf-8") as f:
                        mapping_data = json.load(f)
                except Exception:
                    mapping_data = {}
            
            record_key = f"{mac}_{target_time}"
            mapping_data[record_key] = {
                "original_user_key": user_key,
                "assigned_user_tag": new_tag
            }
            
            with open(mapping_file, "w", encoding="utf-8") as f:
                json.dump(mapping_data, f, ensure_ascii=False, indent=2)
                
        await hass.async_add_executor_job(update_mapping_sync)
        _LOGGER.info(f"[Microlife] Measurement from {target_time} on device {mac} forced to user: {new_tag}")

        for user_data in sensors.values():
            if "history" in user_data and user_data["history"]._mac == mac:
                if hasattr(user_data["history"], "async_force_update_from_cache"):
                    hass.async_create_task(user_data["history"].async_force_update_from_cache())

    async def handle_sync_time(call: ServiceCall):
        """Synchronize device system clock."""
        mac = call.data.get("mac").upper()
        target_sensor = None
        for group in sensors.values():
            if "history" in group and group["history"]._mac == mac:
                target_sensor = group["history"]
                break
        if not target_sensor:
            return
        now = datetime.now()
        year_short = now.year % 100
        time_payload = bytearray([0x4D, 0x3A, 0x00, 0x0F, 0x0D, year_short, now.month, now.day, now.hour, now.minute, now.second])
        time_payload.append(calc_checksum_1byte(time_payload))
        if hasattr(target_sensor, "async_gatt_write"):
            await target_sensor.async_gatt_write(WRITE_UUID, bytes(time_payload))

    async def handle_clear_history(call: ServiceCall):
        """Completely erase memory storage on the physical device."""
        mac = call.data.get("mac").upper()
        user_key = call.data.get("user_key")
        user_no = 0x01 if user_key == "u1" else 0x02
        target_sensor = None
        for key, group in sensors.items():
            if "history" in group and group["history"]._mac == mac and key == user_key:
                target_sensor = group["history"]
                break
        if not target_sensor:
            return
        clear_payload = bytearray([0x4D, 0x3A, 0x00, 0x0A, 0x03, user_no])
        clear_payload.append(calc_checksum_1byte(clear_payload))
        if hasattr(target_sensor, "async_gatt_write"):
            await target_sensor.async_gatt_write(WRITE_UUID, bytes(clear_payload))

    async def handle_export_history(call):
        """Export parsed and filtered diagnostic historical data to a file."""
        target_user = call.data.get("user_name")
        if not target_user:
            return

        start_date_str = call.data.get("start_date")
        end_date_str = call.data.get("end_date")
        export_format = call.data.get("format", "txt")
        try:
            start_dt = datetime.strptime(start_date_str, "%d-%m-%Y") if start_date_str else None
            end_dt = datetime.strptime(end_date_str, "%d-%m-%Y") if end_date_str else None
        except ValueError:
            return
        all_measurements = []
        for u_data in sensors.values():
            if "history" in u_data:
                all_measurements.extend(u_data["history"].extra_state_attributes.get("measurements", []))
        filtered = []
        for m in all_measurements:
            m_tag = m.get("user_tag", "unknown").lower()
            if m_tag != target_user.lower():
                continue
            try:
                m_dt = datetime.strptime(m["datetime"], "%Y-%m-%d %H:%M")
            except (ValueError, TypeError):
                continue
            if start_dt and m_dt < start_dt:
                continue
            if end_dt and m_dt > end_dt.replace(hour=23, minute=59):
                continue
            filtered.append(m)
        filtered.sort(key=lambda x: x.get("datetime", ""))

        def save_file_to_disk():
            export_dir = hass.config.path("www/exports")
            os.makedirs(export_dir, exist_ok=True)
            generated_filename = f"export_{target_user}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{export_format}"
            file_path = os.path.join(export_dir, generated_filename)
            if export_format == "csv":
                with open(file_path, mode="w", encoding="utf-8", newline="") as f:
                    writer = csv.writer(f, delimiter=";")
                    writer.writerow(["Timestamp", "SYS", "DIA", "Pulse", "Arrhythmia", "AFIB", "Cuff", "User"])
                    for row in filtered:
                        writer.writerow([row.get("datetime"), row.get("systolic"), row.get("diastolic"), row.get("pulse"), "Yes" if row.get("arrhythmia") else "No", "Yes" if row.get("afib") else "No", row.get("cuff_status", "OK"), row.get("user_tag", "unknown")])
            else:
                with open(file_path, mode="w", encoding="utf-8") as f:
                    f.write(f"Report for user: {target_user}\n")
                    for row in filtered:
                        f.write(f"{row.get('datetime')} | SYS: {row.get('systolic')} | DIA: {row.get('diastolic')} | Pulse: {row.get('pulse')} | Tag: {row.get('user_tag', 'unknown')}\n")
            return generated_filename

        filename = await hass.async_add_executor_job(save_file_to_disk)
        await hass.services.async_call("persistent_notification", "create", {"title": "📊 Microlife Export", "message": f"Export complete. [/local/exports/{filename}]"})

    hass.services.async_register(DOMAIN, "tag_measurement", handle_tag_measurement)
    hass.services.async_register(DOMAIN, "export_history", handle_export_history)
    hass.services.async_register(DOMAIN, "sync_time", handle_sync_time, schema=SERVICE_CLEAR_SCHEMA)
    hass.services.async_register(DOMAIN, "clear_history", handle_clear_history, schema=SERVICE_CLEAR_SCHEMA)
