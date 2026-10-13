"""Bluetooth transport buffer defragmentation module for Microlife with full verbose logging."""
import asyncio
import logging
import time
from .const import NOTIFY_UUID, WRITE_UUID, OXYGEN_NOTIFY_UUID

_LOGGER = logging.getLogger(__name__)

async def request_history_buffered(client, cmd, device_type) -> bytearray:
    """Buffered read logic mapping StringBuilder from SDK with absolute verbose chunk tracking."""
    buffer = bytearray()
    event = asyncio.Event()
    start_stream_time = time.time()

    def notify_callback(sender, data):
        chunk_time = time.time() - start_stream_time
        buffer.extend(data)
        _LOGGER.debug(
            "[Microlife VERBOSE Buffer] CHUNK RECEIVED! Time offset: %.3f sec | Sender: %s | "
            "Chunk Hex: %s | Chunk Size: %d bytes | Cumulative buffer size: %d bytes",
            chunk_time, sender, data.hex().upper(), len(data), len(buffer)
        )
        event.set()

    target_notify = OXYGEN_NOTIFY_UUID if device_type == "oximeter" else NOTIFY_UUID
    
    _LOGGER.info("[Microlife VERBOSE Buffer] Subscribing to NOTIFY UUID: %s", target_notify)
    await client.start_notify(target_notify, notify_callback)
    _LOGGER.debug("[Microlife VERBOSE Buffer] Notification subscription verified successfully.")
    
    if device_type != "oximeter":
        _LOGGER.info("[Microlife VERBOSE Buffer] Executing write_gatt_char to WRITE UUID: %s | Payload Command Hex: %s", WRITE_UUID, cmd.hex().upper())
        await client.write_gatt_char(WRITE_UUID, cmd, response=True)
        _LOGGER.debug("[Microlife VERBOSE Buffer] Command packet acknowledged by the device controller.")
        
    _LOGGER.info("[Microlife VERBOSE Buffer] Entering chunk aggregation loop. Awaiting packets...")
    
    while True:
        event.clear()
        try:
            loop_start = time.time()
            # Тайм-аут затухания пакетов из вашего скрипта (2.5 секунды)
            # Как только прибор выплюнет всю матрицу за 5 секунд и замолчит — мы мгновенно выходим
            await asyncio.wait_for(event.wait(), timeout=2.5)
            _LOGGER.debug("[Microlife VERBOSE Buffer] Loop awakened by incoming chunk. Arrival delay: %.3f sec", time.time() - loop_start)
            
            if device_type == "oximeter":
                _LOGGER.debug("[Microlife VERBOSE Buffer] Evaluation for oximeter stream. Buffer state: %d/4 bytes", len(buffer))
                if len(buffer) >= 4:
                    _LOGGER.info("[Microlife VERBOSE Buffer] Oximeter telemetry constraint fulfilled. Breaking loop.")
                    break
                continue

            # Сканируем заголовок для отладочного вывода размера полезной нагрузки
            idx = buffer.find(b"\x4d")
            if idx != -1 and idx + 4 <= len(buffer):
                payload_len = int.from_bytes(buffer[idx+2:idx+4], byteorder='big')
                _LOGGER.debug(
                    "[Microlife VERBOSE Buffer] Stream Progress: Header '4D' matched. "
                    "Expected payload from header descriptor: %d bytes. Currently aggregated in buffer: %d bytes.",
                    payload_len, len(buffer)
                )

        except asyncio.TimeoutError:
            # Срабатывает строго тогда, когда поток байт прервался (выгрузка завершена)
            _LOGGER.info(
                "[Microlife VERBOSE Buffer] Stream transmission quiet period detected (2.5s silence). "
                "Data download complete. Total accumulated buffer: %d bytes. Finalizing stream loop.", len(buffer)
            )
            break
            
    _LOGGER.info("[Microlife VERBOSE Buffer] Unsubscribing from NOTIFY UUID: %s", target_notify)
    await client.stop_notify(target_notify)
    _LOGGER.debug("[Microlife VERBOSE Buffer] Notification channel closed. Returning bytearray container to core engine.")
    return buffer
