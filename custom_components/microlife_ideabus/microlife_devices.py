"""Known Microlife Bluetooth devices."""
MICROLIFE_BLUETOOTH_MODELS = (
    "B6 CONNECT",
    "BP B6 CONNECT",
    "BP B4 BT",
    "B4 BT",
    "BP B3 BT",
    "B3 BT",
    "BP B1 BT",
    "B1 BT",
    "BP A7 TOUCH BT",
    "A7 TOUCH BT",
    "BP A6 BT",
    "A6 BT",
    "BP A6 CONNECT",
    "A6 CONNECT",
    "BP 3GY1-2N",
    "3GY1-2N",
    "SERIES 900 BT",
    "900 BT",
    "PREMIUM BT",

    "BP W70 BT",

    "WATCHBP HOME BT",
    "WATCHBP HOME A BT",
    "WATCHBP OFFICE",
    "WATCHBP OFFICE 2G",
    "WATCHBP OFFICE ABI",
    "WATCHBP O3",
    "WATCHBP O3 2G",
    "WATCHBP VITAL",

    "WS 200 BT",
    "WS 80 BT",

    "NC 150 BT",
    "MT 850 BT",

    "PF 100 BT",
    "PF 200 BT",

    "OXY 300 BT",
    "OXY 500 BT",
)

MICROLIFE_SERVICE_UUIDS = {
    "0000fff0-0000-1000-8000-00805f9b34fb",
}


def is_microlife_device(
    name: str,
    service_uuids: set[str],
) -> bool:
    name = (name or "").upper()

    if any(
        model in name
        for model in MICROLIFE_BLUETOOTH_MODELS
    ):
        return True

    return bool(
        {
            uuid.lower()
            for uuid in service_uuids
        }
        & MICROLIFE_SERVICE_UUIDS
    )
