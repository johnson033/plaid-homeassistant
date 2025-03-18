import logging
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, CoordinatorEntity, UpdateFailed
from .api import PlaidAPI
from .const import DOMAIN
from datetime import timedelta
import re 

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(hours=12)  # Set how often to refresh

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Plaid sensors for each linked account."""
    access_token = entry.data.get("access_token", "")
    if not access_token: 
        _LOGGER.error("No access tokens found.")
        return False 
    
    plaid_api = PlaidAPI(entry.data["client_id"], entry.data["client_secret"])  

    async def async_fetch_data():
        """Fetch accounts once for all sensors using the same access token."""
        accounts, institution = await plaid_api.get_accounts(access_token)
        if not accounts:
            raise UpdateFailed("Failed to fetch accounts")

        for account in accounts:
            account['institution'] = institution 
        
        return {"accounts": accounts}
    
    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="plaid_sensor",
        update_method=async_fetch_data,
        update_interval=SCAN_INTERVAL,
    )

    await coordinator.async_config_entry_first_refresh()

    sensors = []
    for account in coordinator.data["accounts"]:
        sensors.append(PlaidAccountSensor(coordinator, account))

    async_add_entities(sensors, True)


class PlaidAccountSensor(CoordinatorEntity, Entity):
    """Representation of a Plaid Account Sensor."""
    def __init__(self, coordinator,  account):
        super().__init__(coordinator)
        self._account_id = account["account_id"] 
        self._name = account["name"]
        self._institution = account["institution"]
        self._balance = account.get("balances", {}).get("current", 0) 
        self._available = account.get("balances", {}).get("available", 0)
        self._limit = account.get("balances", {}).get("limit", 0)
        self._currency_code = account.get("balances", {}).get("iso_currency_code", "USD")
        self._type = account.get("type")
        self._subtype = account.get("subtype")
        self._mask = account.get("mask")
        self._attr_unique_id = self._generate_unique_id()
    
    def _generate_unique_id(self):
        """Generate a unique ID for this sensor."""
        sanitized_institution = self._sanitize(self._institution)
        sanitized_account_id = self._sanitize(self._account_id)
        return f"plaid_{sanitized_institution}_{sanitized_account_id}"
    

    @property
    def should_poll(self):
        """Sensors using DataUpdateCoordinator do not require polling."""
        return False  # ✅ Disable polling


    @property
    def name(self):
        """Return the name of the sensor."""
        name = f"Plaid {self._institution} {self._name}"
        if self._mask:
            name += f" {self._mask}" 
        return name

    @property
    def state(self):
        """Return the latest account balance as the sensor state."""
        account_data = self._get_latest_account_data()
        return account_data.get("balances", {}).get("current", 0)

    @property
    def extra_state_attributes(self):
        """Return extra attributes for more sensor details."""
        account_data = self._get_latest_account_data()
        return {
            "institution": self._institution,
            "name": self._name,
            "available_balance": account_data.get("balances", {}).get("available", 0),
            "credit_limit": account_data.get("balances", {}).get("limit", 0),
            "currency": account_data.get("balances", {}).get("iso_currency_code", "USD"),
            "account_type": account_data.get("type"),
            "account_subtype": account_data.get("subtype"),
            "account_mask": self._mask,
            "account_id": self._account_id
        }

    def _get_latest_account_data(self):
        """Retrieve the latest account data from the shared coordinator."""
        for account in self.coordinator.data["accounts"]:
            if account["account_id"] == self._account_id:
                return account
        return {}  # If not found, return empty dict
    
    def _sanitize(self, value):
        """Sanitize a string to be a valid Home Assistant ID component."""
        return re.sub(r"[^a-zA-Z0-9_]", "_", value.lower())  # ✅ Replace invalid characters