"""User services module for Microlife Ideabus integration."""
import os
import csv
import json
import logging
from datetime import datetime
import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN, calc_checksum_1byte
from .pairing_helper import MicrolifePairingHelper

_LOGGER = logging.getLogger(__name__)

SERVICE_CLEAR_SCHEMA = vol.Schema({
    vol.Required("mac"): cv.string,
    vol.Optional("user_key", default="u1"): vol.In(["u1", "u2"]),
})

SERVICE_REPAIR_SCHEMA = vol.Schema({
    vol.Required("mac"): cv.string,
})

def register_microlife_services(hass: HomeAssistant):
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
        _LOGGER.info("[Microlife] Record from %s on device %s forced to user: %s", target_time, mac, new_tag)

        for entry in hass.config_entries.async_entries(DOMAIN):
            if entry.data.get("mac", "").upper() != mac:
                continue

            runtime = entry.runtime_data

            for group in runtime.sensors.values():
                for entity in group.values():
                    entity.async_write_ha_state()

    async def handle_sync_time(call: ServiceCall):
        """Synchronize device system clock via command queue."""
        mac = call.data.get("mac").upper()
        
        target_entry = None
        for entry in hass.config_entries.async_entries(DOMAIN):
            if entry.data.get("mac", "").upper() == mac:
                target_entry = entry
                break
                
        if not target_entry:
            _LOGGER.error("Device configuration for MAC %s not found", mac)
            return

        # ИСПРАВЛЕНО: Безопасное извлечение очереди из глобального хранилища hass.data
        entry_context = target_entry.runtime_data
        if not entry_context:
            _LOGGER.error("Active execution queue context missing for MAC %s", mac)
            return

        now = datetime.now()
        year_short = now.year % 100
        time_payload = bytearray([0x4D, 0x3A, 0x00, 0x0F, 0x0D, year_short, now.month, now.day, now.hour, now.minute, now.second])
        time_payload.append(calc_checksum_1byte(time_payload))
        
        entry_context.cmd_queue.append(bytes(time_payload))
        _LOGGER.info("[Microlife] Time synchronization frame pushed into session execution queue for %s", mac)

    async def handle_clear_history(call: ServiceCall):
        """Completely erase memory storage on the physical device via command queue."""
        mac = call.data.get("mac").upper()
        user_key = call.data.get("user_key")
        user_no = 0x01 if user_key == "u1" else 0x02
        
        target_entry = None
        for entry in hass.config_entries.async_entries(DOMAIN):
            if entry.data.get("mac", "").upper() == mac:
                target_entry = entry
                break
                
        if not target_entry:
            _LOGGER.error("Device configuration for MAC %s not found", mac)
            return

        # ИСПРАВЛЕНО: Извлечение очереди из глобального хранилища hass.data
        entry_context = target_entry.runtime_data
        if not entry_context:
            _LOGGER.error("Active execution queue context missing for MAC %s", mac)
            return

        clear_payload = bytearray([0x4D, 0x3A, 0x00, 0x0A, 0x03, user_no])
        clear_payload.append(calc_checksum_1byte(clear_payload))
        
        entry_context.cmd_queue.append(bytes(clear_payload))
        _LOGGER.warning("[Microlife] Memory wipe frame for profile %s pushed into queue for %s", user_key, mac)

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

        for entry in hass.config_entries.async_entries(DOMAIN):
            runtime = entry.runtime_data

            for u_data in runtime.sensors.values():
                if "history" in u_data:
                    all_measurements.extend(
                        u_data["history"]
                        .extra_state_attributes
                        .get("measurements", [])
                    )
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
                    writer.writerow([
                      "Timestamp",
                      "SYS",
                      "DIA",
                      "Pulse",
                      "Arrhythmia",
                      "IHB",
                      "AFIB",
                      "MAM",
                      "CuffOK",
                      "User",
                    ])

                    for row in filtered:
                      writer.writerow([
                          row.get("datetime"),
                          row.get("systolic"),
                          row.get("diastolic"),
                          row.get("pulse"),
                          row.get("arrhythmia"),
                          row.get("ihb"),
                          row.get("afib"),
                          row.get("mam"),
                          row.get("cuff_ok"),
                          row.get("user_tag", "unknown"),
                      ])
            else:
                with open(file_path, mode="w", encoding="utf-8") as f:
                    f.write(f"Report for user: {target_user}\n")
                    for row in filtered:
                        f.write(
                            f"{row.get('datetime')} | "
                            f"SYS:{row.get('systolic')} | "
                            f"DIA:{row.get('diastolic')} | "
                            f"PULSE:{row.get('pulse')} | "
                            f"ARR:{row.get('arrhythmia')} | "
                            f"IHB:{row.get('ihb')} | "
                            f"AFIB:{row.get('afib')} | "
                            f"MAM:{row.get('mam')} | "
                            f"CUFF:{row.get('cuff_ok')} | "
                            f"USER:{row.get('user_tag', 'unknown')}\n"
                        )
            return generated_filename

        filename = await hass.async_add_executor_job(save_file_to_disk)
        await hass.services.async_call("persistent_notification", "create", {"title": "📊 Microlife Export", "message": f"Export complete. File location: [/local/exports/{filename}]"})

    async def handle_repair_bluetooth(call: ServiceCall):
        """Start Bluetooth bond repair workflow."""

        mac = call.data.get("mac", "").upper().strip()

        if not mac:
            _LOGGER.error(
                "[Microlife Repair] MAC address not supplied."
            )
            return

        _LOGGER.warning(
            "[Microlife Repair] Starting Bluetooth repair workflow for %s",
            mac,
        )

        helper = MicrolifePairingHelper(mac)

        success = await helper.repair_pairing()

        if success:
            await hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "title": "Microlife Bluetooth Repair",
                    "message": (
                        "Repair workflow started successfully. "
                        "Complete Bluetooth pairing in the Microlife config flow."
                    ),
                },
            )

            _LOGGER.info(
                "[Microlife Repair] Repair workflow started for %s",
                mac,
            )
        else:
            await hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "title": "Microlife Bluetooth Repair",
                    "message": (
                        "Unable to start Bluetooth repair workflow."
                    ),
                },
            )

            _LOGGER.error(
                "[Microlife Repair] Failed to start repair workflow for %s",
                mac,
            )

    if not hass.services.has_service(DOMAIN, "tag_measurement",):hass.services.async_register(DOMAIN, "tag_measurement", handle_tag_measurement)
    if not hass.services.has_service(DOMAIN, "export_history",):hass.services.async_register(DOMAIN, "export_history", handle_export_history)
    if not hass.services.has_service(DOMAIN, "sync_time",):hass.services.async_register(DOMAIN, "sync_time", handle_sync_time, schema=SERVICE_CLEAR_SCHEMA)
    if not hass.services.has_service(DOMAIN, "clear_history",):hass.services.async_register(DOMAIN, "clear_history", handle_clear_history, schema=SERVICE_CLEAR_SCHEMA)
    if not hass.services.has_service(DOMAIN, "repair_bluetooth",):hass.services.async_register(DOMAIN, "repair_bluetooth", handle_repair_bluetooth, schema=SERVICE_REPAIR_SCHEMA)
