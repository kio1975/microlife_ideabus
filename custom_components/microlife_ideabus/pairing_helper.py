"""Isolated background pairing assistant for Microlife Ideabus without multi-process GATT collisions."""
import asyncio
import logging
import re
_LOGGER = logging.getLogger(__name__)


class MicrolifePairingHelper:
    """Manages secure OS-level pairing sessions via bluetoothctl agent layout."""

    def __init__(self, mac_address: str):
        """Initialize the pairing supervisor session."""
        self.mac_address = mac_address.upper().strip()
        self._pairing_task = None
        self.passkey = None

    async def start_pairing_session(self) -> bool:
        """Запуск интерактивного процесса bluetoothctl и инициирование сопряжения."""
        try:
            _LOGGER.info("[Microlife Helper] Spawning interactive pairing daemon shell...")
            self._pairing_task = await asyncio.create_subprocess_exec(
                "bluetoothctl",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

                        
            # Регистрируем агент ввода клавиатуры на шине DBus Linux
            self._pairing_task.stdin.write(b"agent DisplayYesNo\n")
            self._pairing_task.stdin.write(b"default-agent\n")
            self._pairing_task.stdin.write(b"power on\n")
            self._pairing_task.stdin.write(b"pairable on\n")
            
            # Инициируем нативную команду сопряжения BlueZ
            _LOGGER.info("[Microlife Helper] Sending pair command for MAC: %s", self.mac_address)
            self._pairing_task.stdin.write(f"pair {self.mac_address}\n".encode())
            await self._pairing_task.stdin.drain()
 
            
            return True
        except Exception as err:
            _LOGGER.error("[Microlife Helper] Failed to establish interactive BlueZ daemon: %s", err)
            await self.close_session()
            return False
    async def wait_for_passkey(
        self,
        timeout: float = 60.0,
    ) -> bool:

        while True:

            try:
                raw = await asyncio.wait_for(
                    self._pairing_task.stdout.readline(),
                    timeout=timeout,
                )
            except TimeoutError:
                _LOGGER.error(
                    "[Microlife Helper] Passkey timeout."
                )
                return False

            if not raw:
                return False

            text = raw.decode(
                errors="ignore"
            ).strip()

            _LOGGER.error(
                "[Microlife Helper RAW] %r",
                text,
            )

            match = re.search(
                r"Confirm passkey (\d+)",
                text,
            )

            if match:
                self.passkey = match.group(1)

                _LOGGER.warning(
                    "[Microlife Helper] Passkey detected: %s",
                    self.passkey,
                )

                return True

            if "Failed to pair" in text:
                return False
    async def wait_for_pairing_success(self, timeout: float = 60.0) -> bool:
        """Wait for bluetoothctl to report successful pairing."""

        while True:
            try:
                raw = await asyncio.wait_for(
                    self._pairing_task.stdout.readline(),
                    timeout=timeout,
                )
            except TimeoutError:
                _LOGGER.error(
                    "[Microlife Helper] Pairing timeout."
                )
                return False

            if not raw:
                return False

            text = raw.decode(
                errors="ignore"
            ).strip()

            _LOGGER.error(
                "[Microlife Helper RAW] %r",
                text,
            )

            match = re.search(
                r"Confirm passkey (\d+)",
                text,
            )

            if match:
                self.passkey = match.group(1)

                _LOGGER.warning(
                    "[Microlife Helper] Passkey detected: %s",
                    self.passkey,
                )

            if "Pairing successful" in text:
                return True

            if "Bonded: yes" in text:
                return True

            if "Paired: yes" in text:
                return True

            if "Failed to pair" in text:
                return False

    async def confirm_pairing(self,confirmed: bool,) -> bool:
        response = b"yes\n" if confirmed else b"no\n"
        if not self._pairing_task or self._pairing_task.returncode is not None:
            _LOGGER.error("[Microlife Helper] Execution pipeline rejected: background daemon is dead.")
            return False

        try:
            # 1. # Confirm Bluetooth numeric comparison request.
            _LOGGER.info("[Microlife Helper] Confirming Bluetooth passkey...")
            self._pairing_task.stdin.write(response)
            await self._pairing_task.stdin.drain()
            
            # Ждем  пока Linux завершит JustWorks хэндшейк
            _LOGGER.info("[Microlife Helper] Waiting for bluetoothctl pairing confirmation...")
            pairing_ok = await self.wait_for_pairing_success()

            if not pairing_ok:
                _LOGGER.error(
                    "[Microlife Helper] Pairing did not complete."
                )
                return False

            # 2. Выставляем статус доверенного устройства на уровне ОС Linux
            _LOGGER.info("[Microlife Helper] Setting trust flag for MAC: %s", self.mac_address)
            self._pairing_task.stdin.write(
                f"trust {self.mac_address}\n".encode()
            )
            
            await self._pairing_task.stdin.drain()

            await asyncio.sleep(1.0)
            _LOGGER.info("[Microlife Helper] OS-level bonding completed successfully. Finalizing context...")
            return True

        except Exception as err:
            _LOGGER.error("[Microlife Helper] Critical failure inside encryption tunnel: %s", err)
            return False
        finally:
            # Начисто закрываем сессию через вежливый выход
            await self.close_session()

    async def remove_device(self) -> bool:
        """Remove stale BlueZ bond before re-pairing."""

        proc = None

        try:
            _LOGGER.warning(
                "[Microlife Helper] Removing existing bond for %s",
                self.mac_address,
            )

            proc = await asyncio.create_subprocess_exec(
                "bluetoothctl",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            proc.stdin.write(f"remove {self.mac_address}\n".encode())
            await proc.stdin.drain()

            await asyncio.sleep(2.0)

            proc.stdin.write(b"exit\n")
            await proc.stdin.drain()

            return True

        except Exception as err:
            _LOGGER.error(
                "[Microlife Helper] Failed to remove bond: %s",
                err,
            )
            return False

        finally:
            try:
                if proc and proc.returncode is None:
                    proc.kill()
                    await proc.wait()
            except Exception:
                pass

    async def repair_pairing(self) -> bool:

        removed = await self.remove_device()

        if not removed:
            _LOGGER.warning(
                "[Microlife Helper] Bond removal failed, continuing anyway."
            )

        await asyncio.sleep(1.0)

        started = await self.start_pairing_session()

        if not started:
            return False

        return await self.wait_for_passkey()

    async def close_session(self):
        """Штатное вежливое завершение фонового подпроцесса без разрыва стека BlueZ."""
        if self._pairing_task:
            _LOGGER.info("[Microlife Helper] Releasing Bluetooth adapter hardware registers...")
            try:
                if self._pairing_task.returncode is None:
                    # ИСПРАВЛЕНО: Шлём штатную команду утилиты bluetoothctl для корректного 
                    # закрытия BLE-сессии на уровне контроллера. Исключает экстренное мигание прибора.
                    self._pairing_task.stdin.write(b"exit\n")
                    await self._pairing_task.stdin.drain()
                    # Даем полсекунды BlueZ отправить пакет LL_TERMINATE_IND в радиоэфир тонометра
                    await asyncio.sleep(0.5)
            except Exception as pipe_err:
                _LOGGER.debug("[Microlife Helper] Pipe flush skipped: %s", pipe_err)
            finally:
                try:
                    if self._pairing_task.returncode is None:
                        self._pairing_task.kill()
                        await self._pairing_task.wait()
                except Exception:
                    pass
            self._pairing_task = None
            _LOGGER.info("[Microlife Helper] Low-level Bluetooth transport context finalized.")
