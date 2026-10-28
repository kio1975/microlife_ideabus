"""Isolated background pairing assistant for Microlife Ideabus without multi-process GATT collisions."""
import asyncio
import logging
import time
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
        """Start interactive bluetoothctl session and initiate pairing."""
        try:
            _LOGGER.debug("[Microlife Helper] Spawning interactive pairing daemon shell...")
            self._pairing_task = await asyncio.create_subprocess_exec(
                "bluetoothctl",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

                        
            # Register keyboard input agent on the Linux DBus bus.
            self._pairing_task.stdin.write(b"agent DisplayYesNo\n")
            self._pairing_task.stdin.write(b"default-agent\n")
            self._pairing_task.stdin.write(b"power on\n")
            self._pairing_task.stdin.write(b"pairable on\n")

            self._pairing_task.stdin.write(b"scan on\n")
            await self._pairing_task.stdin.drain()

            
            # Initiate native BlueZ pairing command.
            _LOGGER.debug("[Microlife Helper] Sending pair command for MAC: %s", self.mac_address)
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
        """Detect passkey immediately without waiting for newline."""

        pattern = re.compile(
            r"Confirm passkey (\d+)"
        )

        buffer = ""

        deadline = (
            asyncio.get_running_loop().time()
            + timeout
        )

        while (
            asyncio.get_running_loop().time()
            < deadline
        ):

            try:
                chunk = await asyncio.wait_for(
                    self._pairing_task.stdout.read(128),
                    timeout=1.0,
                )

            except TimeoutError:
                continue

            if not chunk:
                return False

            text = chunk.decode(
                errors="ignore"
            )

            buffer += text

            _LOGGER.debug(
                "[Microlife Helper RAW] %r",
                text,
            )

            match = pattern.search(
                buffer
            )

            if match:
                self.passkey = match.group(1)

                _LOGGER.info(
                    "[Microlife Helper] Passkey detected: %s",
                    self.passkey,
                )

                return True

            if (
                "Failed to pair" in buffer
                or "AuthenticationCanceled" in buffer
            ):
                return False

            if len(buffer) > 4096:
                buffer = buffer[-2048:]

        _LOGGER.error(
            "[Microlife Helper] Passkey timeout."
        )

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

            _LOGGER.debug(
                "[Microlife Helper RAW] %r",
                text,
            )

            match = re.search(
                r"Confirm passkey (\d+)",
                text,
            )

            if match:
                continue

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
            # Confirm Bluetooth numeric comparison request.
            _LOGGER.info("[Microlife Helper] Confirming Bluetooth passkey...")
            self._pairing_task.stdin.write(response)
            await self._pairing_task.stdin.drain()
            
            # Wait for Linux to complete the JustWorks handshake.
            _LOGGER.debug("[Microlife Helper] Waiting for bluetoothctl pairing confirmation...")
            start = time.monotonic()
            
            pairing_ok = await self.wait_for_pairing_success()

            _LOGGER.debug(
                "[PAIRING TIMING] pairing confirmation took %.2f sec",
                time.monotonic() - start,
            )
            if not pairing_ok:
                _LOGGER.error(
                    "[Microlife Helper] Pairing did not complete."
                )
                return False

            # Mark device as trusted at the operating system level.
            _LOGGER.info("[Microlife Helper] Setting trust flag for MAC: %s", self.mac_address)
            self._pairing_task.stdin.write(
                f"trust {self.mac_address}\n".encode()
            )
            
            await self._pairing_task.stdin.drain()

            await asyncio.sleep(1.5)
            _LOGGER.info("[Microlife Helper] OS-level bonding completed successfully. Finalizing context...")
            return True

        except Exception as err:
            _LOGGER.error("[Microlife Helper] Critical failure inside encryption tunnel: %s", err)
            return False
        finally:
            # Cleanly terminate pairing session.
            await self.close_session()

    async def remove_device(self) -> bool:
        """Remove stale BlueZ bond before re-pairing."""

        proc = None

        try:
            _LOGGER.debug(
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
        
        started = await self.start_pairing_session()

        if not started:
            return False

        return await self.wait_for_passkey()

    async def close_session(self):
        """Gracefully terminate background bluetoothctl session."""
        if self._pairing_task:
            _LOGGER.debug("[Microlife Helper] Releasing Bluetooth adapter hardware registers...")
            try:
                if self._pairing_task.returncode is None:
                    # Use native bluetoothctl exit command to gracefully
                    # close BLE session on the controller side.
                    self._pairing_task.stdin.write(b"exit\n")
                    await self._pairing_task.stdin.drain()
                    # Give BlueZ time to transmit LL_TERMINATE_IND.
                    await asyncio.sleep(1.5)
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
            _LOGGER.debug("[Microlife Helper] Low-level Bluetooth transport context finalized.")
