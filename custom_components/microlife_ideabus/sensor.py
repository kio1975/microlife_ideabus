"""Sensor platform core engine for Microlife Ideabus multi-device integration compliant with HA Core 2026.10."""
import asyncio
import logging
import copy
from datetime import datetime
from homeassistant.core import HomeAssistant, callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.components.bluetooth import (
    async_register_callback,
    async_ble_device_from_address,
    BluetoothScanningMode,
    BluetoothServiceInfoBleak
)
from homeassistant.helpers.device_registry import DeviceInfo
from bleak_retry_connector import establish_connection, BleakClientWithServiceCache

# Гарантированный импорт констант и функций устройства
from .const import DOMAIN, NOTIFY_UUID, WRITE_UUID, build_microlife_command, OXYGEN_NOTIFY_UUID
from .device import get_microlife_device_info

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Динамическая инициализация датчиков на основе выбранного типа оборудования."""
    mac = entry.data.get("mac", "EF:06:40:CE:23:8E").upper()
    device_type = entry.data.get("device_type", "blood_pressure")
    _LOGGER.info("[Microlife 2026 Core] Инициализация платформы. Режим: %s | MAC: %s", device_type, mac)

    if device_type == "wbo_scale":
        sensors = {
            "u1": {
                "weight": MicrolifeSensor(entry, "weight", "Weight", "kg", mac, SensorDeviceClass.WEIGHT),
                "fat": MicrolifeSensor(entry, "fat", "Body Fat", "%", mac),
                "water": MicrolifeSensor(entry, "water", "Body Water", "%", mac),
                "muscle": MicrolifeSensor(entry, "muscle", "Muscle Mass", "kg", mac),
                "history": MicrolifeSensor(entry, "wbo_hist", "Scale Full Archive", None, mac)
            }
        }
    elif device_type == "oximeter":
        sensors = {
            "u1": {
                "spo2": MicrolifeSensor(entry, "spo2", "SpO2 Saturation", "%", mac),
                "pulse": MicrolifeSensor(entry, "pulse", "Oximeter Pulse", "bpm", mac),
                "pi": MicrolifeSensor(entry, "pi", "Perfusion Index PI", "%", mac)
            }
        }
    elif device_type == "thermometer":
        sensors = {
            "u1": {
                "temperature": MicrolifeSensor(entry, "temperature", "Temperature", "°C", mac, SensorDeviceClass.TEMPERATURE)
            }
        }
    else:
        sensors = {
            "u1": {
                "systolic": MicrolifeSensor(entry, "u1_sys", "Пользователь 1 Систолическое", "мм рт.ст.", mac),
                "diastolic": MicrolifeSensor(entry, "u1_dia", "Пользователь 1 Диастолическое", "мм рт.ст.", mac),
                "pulse": MicrolifeSensor(entry, "u1_pulse", "Пользователь 1 Пульс", "уд/мин", mac),
                "time": MicrolifeSensor(entry, "u1_time", "Пользователь 1 Время замера", None, mac, SensorDeviceClass.TIMESTAMP),
                "history": MicrolifeSensor(entry, "u1_hist", "Пользователь 1 Полный Архив", None, mac)
            },
            "u2": {
                "systolic": MicrolifeSensor(entry, "u2_sys", "Пользователь 2 Систолическое", "мм рт.ст.", mac),
                "diastolic": MicrolifeSensor(entry, "u2_dia", "Пользователь 2 Диастолическое", "мм рт.ст.", mac),
                "pulse": MicrolifeSensor(entry, "u2_pulse", "Пользователь 2 Пульс", "уд/мин", mac),
                "time": MicrolifeSensor(entry, "u2_time", "Пользователь 2 Время замера", None, mac, SensorDeviceClass.TIMESTAMP),
                "history": MicrolifeSensor(entry, "u2_hist", "Пользователь 2 Полный Архив", None, mac)
            }
        }

    entities = []
    for user_data in sensors.values():
        entities.extend(user_data.values())
    async_add_entities(entities)

    # Словарь состояний блокировки для безопасного Event Loop
    state_lock = {"is_connecting": False}

    @callback
    def _bluetooth_callback(service_info: BluetoothServiceInfoBleak, change):
        if state_lock["is_connecting"]:
            return
        state_lock["is_connecting"] = True
        
        # Запуск задачи с передачей контейнера блокировки
        hass.async_create_task(_connect_and_fetch_worker(hass, sensors, mac, device_type, service_info, state_lock))

    entry.async_on_unload(async_register_callback(hass, _bluetooth_callback, {"address": mac}, BluetoothScanningMode.ACTIVE))
async def _connect_and_fetch_worker(hass, sensors, mac, device_type, service_info, state_lock):
    """Сквозной воркер сессии связи для локального адаптера hci0 с интеграцией в habluetooth layer."""
    # Импортируем легитимный коннектор ядра и базовый бэкенд BleakClient
    from bleak import BleakClient
    from bleak_retry_connector import establish_connection
    source = getattr(service_info, "source", "local")
    
    # ВАШЕ ОРИГИНАЛЬНОЕ РАЗВЕДЕНИЕ АДАПТЕРОВ ПО ВРЕМЕНИ (Защита от GATT 133 коллизий)
    if "hci" not in str(source).lower():
        await asyncio.sleep(1.0)
    else:
        await asyncio.sleep(0.3)

    _LOGGER.info(f"[Microlife Ideabus] Обнаружен прибор через локальный адаптер {source}. Подключение...")
    try:
        # ИСПРАВЛЕНО ДЛЯ HCI0: Используем establish_connection для прохождения через D-Bus брокер ядра,
        # но передаем туда сырой BleakClient, что заставит локальный hci0 честно вычитать сервисы прибора!
        client = await establish_connection(
            BleakClient,
            service_info.device,
            "Microlife B6 Connect",
            max_attempts=3,
            timeout=15.0
        )
        
        try:
            _LOGGER.info("[Microlife Ideabus] Защищенный канал связи hci0 открыт. Выгрузка Flash-матрицы...")
            await asyncio.sleep(0.5)
            
            # --- УНИВЕРСАЛЬНЫЙ МУЛЬТИПРИБОРНЫЙ РОУТИНГ ПО СТАНДАРТУ SDK ---
            if device_type == "wbo_scale":
                cmd = build_microlife_command("wbo_scale", 1)
                data = await request_history(client, cmd, device_type)
                from .ui_dispatch import update_scale_sensors
                update_scale_sensors(sensors["u1"], data)
            elif device_type == "oximeter":
                data = await request_history(client, b"", device_type)
                from .ui_dispatch import update_oximeter_sensors
                update_oximeter_sensors(sensors["u1"], data)
            elif device_type == "thermometer":
                cmd = build_microlife_command("thermometer", 1)
                data = await request_history(client, cmd, device_type)
                from .ui_dispatch import update_thermo_sensors
                update_thermo_sensors(sensors["u1"], data)
            else:
                # --- АВТОМАТИЧЕСКИЙ МАРШРУТ ЧЕРЕЗ ВАШУ ФАБРИКУ КОМАНД ---
                _LOGGER.info("[Microlife Диагностика] Запрос архива Пользователя 1...")
                cmd_u1 = build_microlife_command(device_type, 1)
                data_u1 = await request_history(client, cmd_u1, device_type)
                _LOGGER.info(f"[Microlife Диагностика] От Пользователя 1 получено сырых байт: {len(data_u1)}")
                
                records_u1 = parse_ideabus_matrix(data_u1)
                _LOGGER.info(f"[Microlife Диагностика] Успешно распарсено замеров Пользователя 1: {len(records_u1)}")
                if records_u1:
                    update_user_sensors_with_history(sensors["u1"], records_u1, "Пользователь 1")
                
                # Стабилизационная пауза для очистки радиомодуля тонометра
                await asyncio.sleep(1.0)
                
                _LOGGER.info("[Microlife Диагностика] Запрос архива Пользователя 2...")
                cmd_u2 = build_microlife_command(device_type, 2)
                data_u2 = await request_history(client, cmd_u2, device_type)
                _LOGGER.info(f"[Microlife Диагностика] От Пользователя 2 получено сырых байт: {len(data_u2)}")
                
                records_u2 = parse_ideabus_matrix(data_u2)
                _LOGGER.info(f"[Microlife Диагностика] Успешно распарсено замеров Пользователя 2: {len(records_u2)}")
                if records_u2:
                    update_user_sensors_with_history(sensors["u2"], records_u2, "Пользователь 2")
                
        finally:
            await client.disconnect()
            _LOGGER.info("[Microlife Ideabus] Данные выгружены, локальная сессия закрыта.")
            
    except Exception as err:
        _LOGGER.error(f"[Microlife Ideabus] Критическая ошибка воркера локальной BLE-сессии hci0 с трассировкой:", exc_info=True)
    finally:
        await asyncio.sleep(20.0)
        state_lock["is_connecting"] = False

async def request_history(client, cmd: bytes, device_type: str) -> bytearray:
    """Универсальная функция выгрузки, полностью совместимая с Bluetooth Proxy."""
    received = bytearray()
    event = asyncio.Event()

    def callback(characteristic, data: bytes):
        received.extend(data)
        _LOGGER.warning("[Microlife VERBOSE Buffer] RX CHUNK! Получено: %d байт | Всего: %d байт", len(data), len(received))
        event.set()

    target_notify = OXYGEN_NOTIFY_UUID if device_type == "oximeter" else NOTIFY_UUID
    await client.start_notify(target_notify, callback)
    await asyncio.sleep(0.5)
    
    if device_type != "oximeter":
        is_response_required = False if device_type in ["wbo_scale", "thermometer"] else True
        await client.write_gatt_char(WRITE_UUID, cmd, response=is_response_required)
    
    while True:
        event.clear()
        try:
            await asyncio.wait_for(event.wait(), timeout=2.5)
        except asyncio.TimeoutError:
            break
            
    try:
        await client.stop_notify(target_notify)
    except Exception: pass
    return received
def parse_ideabus_matrix(raw_bytes) -> list:
    """Оригинальный парсер скользящего окна со смещением i+=1 при промахе паттерна."""
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


def update_user_sensors_with_history(user_sensors, records, user_label="Неизвестный"):
    """Оригинальная функция наполнения Lovelace-датчиков манометра."""
    if not records:
        return
        
    records.sort(key=lambda x: x["_sort"], reverse=True)
    newest = records[0]
    dt_obj = newest["time_obj"]
    timestamp_str = dt_obj.isoformat()
    
    _LOGGER.info(f"[Microlife Сборка JSON] Пишем состояние базовых датчиков {user_label}: SYS={newest['sys']}, DIA={newest['dia']}")
    user_sensors["systolic"].update_state(newest["sys"], timestamp_str)
    user_sensors["diastolic"].update_state(newest["dia"], timestamp_str)
    user_sensors["pulse"].update_state(newest["pulse"], timestamp_str)
    user_sensors["time"].update_state(dt_obj, timestamp_str)
    
    history_list = []
    for r in records:
        history_list.append({
            "datetime": r["time_str"],
            "systolic": r["sys"],
            "diastolic": r["dia"],
            "pulse": r["pulse"]
        })
        
    user_sensors["history"].update_history_state(len(history_list), history_list)


class MicrolifeSensor(SensorEntity):
    """Синтаксически верное представление сущности сенсора Microlife."""
    def __init__(self, entry, key, name, unit, mac, device_class=None):
        self._entry = entry
        self._key = key
        self._name = name
        self._unit = unit
        self._attr_device_class = device_class
        self._state = None
        self._attrs = {}
        self._mac = str(mac).upper()

    @property
    def name(self): return f"Microlife {self._name}"
    @property
    def unique_id(self): return f"microlife_ideabus_{self._entry.entry_id}_{self._key}"
    @property
    def state(self): return self._state
    @property
    def extra_state_attributes(self): return self._attrs
    @property
    def unit_of_measurement(self): return self._unit

    # Полностью восстановленная привязка к твоему внешнему файлу device.py
    @property
    def device_info(self) -> DeviceInfo:
        return get_microlife_device_info(self._mac, "blood_pressure")

    def update_state(self, value, timestamp_str):
        self._state = value
        self._attrs = {"measurement_time": timestamp_str}
        if self.hass: self.async_write_ha_state()

    def update_history_state(self, count, history_data):
        self._state = count
        self._attrs = {"measurements": copy.deepcopy(history_data)}
        if self.hass: self.async_write_ha_state()
