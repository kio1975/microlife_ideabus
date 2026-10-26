"""Buffered BLE streaming and notification worker for Microlife Ideabus."""

import asyncio
import logging

from .const import (
    NOTIFY_UUID,
    WRITE_UUID,
    OXYGEN_NOTIFY_UUID,
    OXYGEN_WRITE_UUID,
)

_LOGGER = logging.getLogger(__name__)


async def request_history_buffered(
    client,
    cmd: bytes,
    device_type: str,
) -> bytearray:
    """Universal buffered BLE history collector."""

    buffer = bytearray()
    queue = asyncio.Queue()

    def _notification_handler(*args):
        if not args:
            return

        try:
            raw_data = args[-1]
            clean_chunk = bytearray(raw_data)

            if clean_chunk:
                _LOGGER.debug(
                    "[Microlife Stream] RX Chunk segment: %s | Size: %s bytes",
                    clean_chunk.hex().upper(),
                    len(clean_chunk),
                )

                queue.put_nowait(clean_chunk)

        except Exception as handler_err:
            _LOGGER.error(
                "[Microlife Stream] Callback processing error: %s",
                handler_err,
            )

    if device_type == "oximeter":
        target_notify_uuid = OXYGEN_NOTIFY_UUID
        target_write_uuid = OXYGEN_WRITE_UUID
    else:
        target_notify_uuid = NOTIFY_UUID
        target_write_uuid = WRITE_UUID

    char_obj = client.services.get_characteristic(
        target_notify_uuid
    )

    if not char_obj:
        _LOGGER.error(
            "[Microlife Stream] Critical: GATT Characteristic %s not found!",
            target_notify_uuid,
        )
        return buffer
    try:
        await client.start_notify(
            char_obj,
            _notification_handler,
        )

        _LOGGER.debug(
            "[Microlife Stream] Notification subscription active."
        )

    except Exception as notify_err:

        _LOGGER.debug(
            "[Microlife Stream] Notification subscription failed: %s",
            notify_err,
        )

        return buffer

    _LOGGER.debug(
        "[Microlife Stream] Waiting 4.0s for device handshake and initial status packets..."
    )

    await asyncio.sleep(2.0)

    if cmd:

        write_char = client.services.get_characteristic(
            target_write_uuid
        )

        if not write_char:

            _LOGGER.error(
                "[Microlife Stream] Write characteristic %s not found!",
                target_write_uuid,
            )

            try:
                await client.stop_notify(char_obj)
            except Exception:
                pass

            return buffer

        _LOGGER.debug(
            "CMD HEX = %s",
            bytearray(cmd).hex().upper(),
        )

        _LOGGER.debug(
            "CMD LEN = %s",
            len(cmd),
        )

        _LOGGER.debug(
            "WRITE UUID = %s",
            target_write_uuid,
        )

        _LOGGER.debug(
            "WRITE CHAR OBJECT = %s",
            write_char,
        )

        _LOGGER.debug(
            "WRITE CHAR PROPERTIES = %s",
            getattr(write_char, "properties", None),
        )

        _LOGGER.debug(
            "CONNECTED = %s",
            client.is_connected,
        )

        _LOGGER.debug(
            "WRITE RESPONSE MODE = True"
        )

        _LOGGER.debug(
            "TEST BEFORE HISTORY"
        )

        try:

            await asyncio.wait_for(
                client.write_gatt_char(
                    write_char,
                    bytearray(cmd),
                    response=True,
                ),
                timeout=3.0,
            )

            _LOGGER.debug(
                "TEST AFTER HISTORY"
            )

        except Exception as write_err:

            _LOGGER.exception(
                "[Microlife Stream] WRITE FAILED TYPE=%s REPR=%r",
                type(write_err).__name__,
                write_err,
            )

            try:
                await client.stop_notify(char_obj)
            except Exception:
                pass

            return buffer

        _LOGGER.debug(
            "CONNECTED = %s",
            client.is_connected,
        )

    else:

        _LOGGER.warning(
            "[Microlife Stream] Empty command received, skipping write phase."
        )

    _LOGGER.debug(
        "[Microlife Stream] Entering queue-based streaming loop. Awaiting history frames..."
    )

    try:

        while True:

            try:

                chunk = await asyncio.wait_for(
                    queue.get(),
                    timeout=3.0,
                )

                buffer.extend(chunk)

            except asyncio.TimeoutError:

                _LOGGER.info(
                    "[Microlife Stream] Inbound transmission window closed (idle timeout reached)."
                )

                break

    finally:

        try:
            await client.stop_notify(char_obj)
        except Exception:
            pass

    return buffer
