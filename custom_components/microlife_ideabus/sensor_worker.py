"""Bluetooth connection and telemetry download worker engine for Microlife."""
import asyncio
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import async_ble_device_from_address

from .const import (
    DOMAIN, 
    WRITE_UUID, 
    build_microlife_command,
    CHAR_MANUFACTURER,
    CHAR_MODEL,
    CHAR_SERIAL,
    UUID_FIRMWARE
)
from .ble_stream import request_history_buffered 
from .parsers.matrix_parser import parse_ideabus_matrix
from .ui_dispatch import (
    update_bpm_user1, update_bpm_user2, update_scale_sensors,
    update_oximeter_sensors, update_thermo_sensors
)

_LOGGER = logging.getLogger(__name__)

def classify_ble_error(err: Exception) -> str:
    """Classify BLE transport failures for diagnostics and future repair."""

    msg = str(err).lower()

    if (
        "authentication" in msg
        or "authentication failure" in msg
        or "pairing" in msg
        or "not paired" in msg
    ):
        return "authentication_failed"

    if "failed to discover services" in msg:
        return "service_discovery_failed"

    if "br-connection-canceled" in msg:
        return "connection_canceled"

    if "not connected" in msg:
        return "not_connected"

    if "in progress" in msg:
        return "stack_busy"

    if "org.bluez.error.inprogress" in msg:
        return "stack_busy"

    if "failed to connect" in msg:
        return "connect_failed"

    if "device disconnected" in msg:
        return "device_disconnected"

    if "timeout" in msg:
        return "timeout"

    return "unknown"

async def connect_and_fetch_worker(hass, entry: ConfigEntry, sensors: dict, mac: str, device_type: str, service_info, state_lock: dict):
    """End-to-end communication session worker optimized for multi-device matrix architecture."""
    _LOGGER.debug(
        "[WORKER ENTER] "
        "mac=%s "
        "device_type=%s "
        "is_connecting=%s",
        mac,
        device_type,
        state_lock.get("is_connecting"),
    )
    ble_device = async_ble_device_from_address(
        hass,
        mac,
        connectable=True,
    )
    _LOGGER.debug(
        "[WORKER] BLE_DEVICE=%r",
        ble_device,
    )

    _LOGGER.debug(
        "[WORKER] SERVICE_INFO=%r",
        service_info,
    )

    _LOGGER.debug(
        "[WORKER] ADDRESS=%s RSSI=%s",
        getattr(service_info, "address", None),
        getattr(service_info, "rssi", None),
    )
    _LOGGER.debug(
        "[BLE DEVICE DETAILS] %r",
        ble_device,
    )    
    entry_context = hass.data.setdefault(
        DOMAIN,
        {}
    ).setdefault(
        entry.entry_id,
        {}
    )

    ble_error_stats = entry_context.setdefault(
        "ble_error_stats",
        {
            "authentication_failed": 0,
            "service_discovery_failed": 0,
            "connection_canceled": 0,
            "not_connected": 0,
            "stack_busy": 0,
            "connect_failed": 0,
            "device_disconnected": 0,
            "timeout": 0,
            "unknown": 0,
        },
    )

    if not ble_device:
        _LOGGER.error(
            "[WORKER EXIT] DEVICE NOT FOUND IN CACHE"
        )

        state_lock["is_connecting"] = False

        _LOGGER.error(
            "[CONNECT LOCK SET FALSE] DEVICE NOT FOUND"
        )

        return

    _LOGGER.debug("[Microlife Connection] Initializing link for hardware platform: %s", mac)
    
    # Launch a background BlueZ agent for automatic encryption request approval
    agent_task = None
    try:
        agent_task = await asyncio.create_subprocess_exec(
            "bluetoothctl",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        agent_task.stdin.write(b"agent NoInputNoOutput\n")
        agent_task.stdin.write(b"default-agent\n")
        await agent_task.stdin.drain()
    except Exception as agent_err:
        _LOGGER.debug("[Microlife Worker] Background agent spawn skipped: %s", agent_err)

    try:
        from bleak_retry_connector import establish_connection, BleakClientWithServiceCache, BleakConnectionError
        _LOGGER.debug(
            "[WORKER] CONNECT START"
        )
        _LOGGER.debug(
            "[BLE CONNECT ATTEMPT] "
            "mac=%s "
            "max_attempts=3 "
            "timeout=15",
            mac,
        )
        # Connect using the service-caching BLE client
        client = await establish_connection(
            BleakClientWithServiceCache, ble_device, f"Microlife {device_type.upper()}",
            max_attempts=3, timeout=15.0, dangerous_use_bleak_cache=False
        )
        _LOGGER.debug(
            "[WORKER] CONNECT SUCCESS client=%r",
            client,
        )
        _LOGGER.debug(
            "[CLIENT STATE] connected=%s",
            client.is_connected,
        )
        if not client.is_connected:
            _LOGGER.error("[Microlife Connection] Link reported success, but client.is_connected is False!")
            _LOGGER.error(
                "[WORKER EXIT]"
            )
            return

        _LOGGER.debug("[Microlife Connection] BLE link established successfully. Connecting secure layer...")

        try:
            # Allow the BLE link to stabilize
            await asyncio.sleep(1.5)

            # Warm up GATT descriptors to initialize the encrypted link state
            _LOGGER.debug("[Microlife Worker] Warming up GATT descriptors and restoring security keys...")
            try:
                descriptors_pool = [CHAR_MANUFACTURER, CHAR_MODEL, CHAR_SERIAL, UUID_FIRMWARE]
                for char_uuid in descriptors_pool:
                    if not client.is_connected:
                        break
                    raw_info = await client.read_gatt_char(char_uuid)
                    _LOGGER.debug("[Microlife Info Sync] Descriptor %s read successful: %s", char_uuid[:8], raw_info.decode(errors="ignore").strip())
                    await asyncio.sleep(0.1)
            except Exception as sync_err:
                _LOGGER.debug("[Microlife Worker] Non-critical info sync bypass: %s", sync_err)

            # Delay before command transmission according to UART buffer requirements
            _LOGGER.debug("[Microlife Worker] Applying Smali SDK 1.0s pre-command buffer flush delay...")
            await asyncio.sleep(1.0)
            
            if not client.is_connected:
                _LOGGER.error("[Microlife Worker] Device disconnected before starting download pipeline.")
                _LOGGER.error(
                    "[WORKER EXIT]"
                )
                return
            
            # Process queued service commands
            entry_context = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})
            queue = entry_context.get("cmd_queue", [])
            
            while queue:
                if not client.is_connected:
                    break
                pending_cmd = queue.pop(0)
                _LOGGER.debug("[Microlife Queue] Executing queued service frame: %s", pending_cmd.hex().upper())
                await client.write_gatt_char(WRITE_UUID, pending_cmd, response=True)
                await asyncio.sleep(0.5)
            
            if not client.is_connected:
                _LOGGER.error("[Microlife Worker] Device disconnected before starting download pipeline.")
                _LOGGER.error(
                    "[WORKER EXIT]"
                )

                return

            _LOGGER.info("[Microlife Worker] Downloading flash memory matrix via secured channel...")
            
            async with asyncio.timeout(30.0):
                if device_type == "wbo_scale":
                    cmd = build_microlife_command("wbo_scale", 1)
                    data = await request_history_buffered(client, cmd, device_type)
                    records = parse_ideabus_matrix(data, "wbo_scale")
                    update_scale_sensors(sensors["u1"], records)
                elif device_type == "oximeter":
                    data = await request_history_buffered(client, b"", device_type)
                    records = parse_ideabus_matrix(data, "oximeter")
                    update_oximeter_sensors(sensors["u1"], records)
                elif device_type == "thermometer":
                    cmd = build_microlife_command("thermometer", 1)
                    data = await request_history_buffered(client, cmd, device_type)
                    records = parse_ideabus_matrix(data, "thermometer")
                    update_thermo_sensors(sensors["u1"], records)
                else:
                    _LOGGER.info("[Microlife Worker] Step 1: Requesting User 1 Matrix array...")
                    cmd_u1 = build_microlife_command(device_type, 1)
                    
                    data_u1 = await request_history_buffered(client, cmd_u1, device_type)
                    _LOGGER.info("[Microlife Worker] User 1 raw buffer received. Size: %s bytes", len(data_u1) if data_u1 else 0)
                    
                    records_u1 = parse_ideabus_matrix(data_u1, device_type)
                    _LOGGER.debug("DEBUG sensors type=%s", type(sensors))
                    _LOGGER.debug("DEBUG sensors=%r", sensors)
                    _LOGGER.debug("DEBUG sensor keys=%s", list(sensors.keys()))
                    _LOGGER.debug("DEBUG records_u1 count=%s", len(records_u1))
                    update_bpm_user1(hass, mac, sensors, records_u1)
                    
                    _LOGGER.debug("[Microlife Worker] Applying mandatory 2.0s SDK memory stabilization cooldown...")
                    await asyncio.sleep(2.0)
                    
                    if not client.is_connected:
                        _LOGGER.error("[Microlife Worker] Device disconnected before Step 2 User 2 request.")
                        _LOGGER.error(
                            "[WORKER EXIT]"
                        )
                        return

                    _LOGGER.info("[Microlife Worker] Step 2: Requesting User 2 Matrix array...")
                    cmd_u2 = build_microlife_command(device_type, 2)
                    data_u2 = await request_history_buffered(client, cmd_u2, device_type)
                    _LOGGER.info("[Microlife Worker] User 2 raw buffer received. Size: %s bytes", len(data_u2) if data_u2 else 0)
                    
                    records_u2 = parse_ideabus_matrix(data_u2, device_type)
                    update_bpm_user2(hass, mac, sensors, records_u2)
                
        except TimeoutError:
            _LOGGER.error("[Microlife Worker] Download session timed out. Hardware did not respond in 30s.")
        finally:
            _LOGGER.debug("[Microlife Connection] Disconnecting BLE transport layer...")
            _LOGGER.debug("[BLE DISCONNECT START]")

            await client.disconnect()

            _LOGGER.debug(
                "[BLE DISCONNECT DONE]"
            )
            bluetooth.async_clear_advertisement_history(
                hass,
                mac,
            )
            _LOGGER.debug(
                "[ADV HISTORY CLEARED] %s",
                mac,
            )
            _LOGGER.debug("[Microlife Worker] Secured BLE session finalized cleanly.")
            
    except (BleakConnectionError, Exception) as err:

        error_type = classify_ble_error(err)

        ble_error_stats[error_type] = (
            ble_error_stats.get(error_type, 0) + 1
        )

        _LOGGER.warning(
            "[Microlife Worker] BLE error statistics: %s",
            ble_error_stats,
        )

        _LOGGER.error(
            "[Microlife Worker] BLE session failed. "
            "TYPE=%s ERROR=%s",
            error_type,
            err,
        )

        if error_type in (
            "authentication_failed",
            "service_discovery_failed",
            "connection_canceled",
        ):
            _LOGGER.error(
                "[Microlife Worker] Possible BLE bond corruption detected. "
                "Device may require re-pairing."
            )

    finally:
        _LOGGER.debug(
            "[WORKER FINALLY ENTER]"
        )
        # terminate the background bluetoothctl agent
        if agent_task:
            try:
                if agent_task.returncode is None:
                    agent_task.stdin.write(b"exit\n")
                    await agent_task.stdin.drain()
                    agent_task.kill()
                    await agent_task.wait()
            except Exception:
                pass
            
        _LOGGER.info("[Microlife Worker] Cooldown lock active for 20 seconds...")
        _LOGGER.debug("[COOLDOWN START]")
        await asyncio.sleep(20.0)
        _LOGGER.debug("[COOLDOWN END]")
        state_lock["is_connecting"] = False
        _LOGGER.debug(
            "[CONNECT LOCK SET FALSE]"
        )

        _LOGGER.debug(
            "[CONNECT LOCK VALUE] %s",
            state_lock.get("is_connecting"),
        )
