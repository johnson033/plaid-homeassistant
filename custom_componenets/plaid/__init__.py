import logging
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

DOMAIN = "plaid_integration"
_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the Plaid integration from a config entry."""

    hass.data.setdefault(DOMAIN, {})
    
    # ✅ Store the config entry's data inside `hass.data`
    hass.data[DOMAIN][entry.entry_id] = {
        "access_tokens": entry.data.get("access_tokens", []),
    }

    # ✅ Forward setup to sensor platform
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle unloading of a config entry."""

    # ✅ Remove integration data when it's unloaded
    if entry.entry_id in hass.data[DOMAIN]:
        del hass.data[DOMAIN][entry.entry_id]

    return await hass.config_entries.async_unload_platforms(entry, ["sensor"])
