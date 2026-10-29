from pathlib import Path

from homeassistant.components.frontend import DATA_PANELS, async_remove_panel
from homeassistant.components.http import StaticPathConfig
from homeassistant.components.panel_custom import (
    async_register_panel as register_custom_panel,
)
from homeassistant.core import HomeAssistant

PANEL_PATH = Path(__file__).parent / "frontend" / "dist"
PANEL_URL = "/microlife_static"


async def async_register_panel(hass: HomeAssistant) -> None:
    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(
                PANEL_URL,
                str(PANEL_PATH),
                False,
            )
        ]
    )

    if "microlife" in hass.data.get(DATA_PANELS, {}):
        async_remove_panel(hass, "microlife")

    await register_custom_panel(
        hass,
        frontend_url_path="microlife",
        webcomponent_name="microlife-panel",
        sidebar_title="Microlife",
        sidebar_icon="mdi:heart-pulse",
        module_url=f"{PANEL_URL}/microlife-dashboard.js",
        embed_iframe=False,
        trust_external=False,
        require_admin=False,
    )