import logging
import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers.selector import SelectSelector, SelectSelectorConfig, SelectSelectorMode
from homeassistant.core import callback
from .const import DOMAIN, PLAID_API_BASE_URL
from .api import PlaidAPI 

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema({
    vol.Required("client_id"): str,
    vol.Required("client_secret"): str
})

class PlaidConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Plaid integration."""

    VERSION = 1 

    async def async_step_user(self, user_input=None): 
        """Step 1. Ask the user for API Credentials, Client id, and client secret""" 

        # If we have existing entries, we can continue and just add a new entry for a new account/institution 
        exiting_entries = self._async_current_entries()    
        if exiting_entries:  
            master_entry = exiting_entries[0] 
            self.client_id = master_entry.data.get("client_id", "")  
            self.client_secret = master_entry.data.get("client_secret", "") 
            # Confirm we have the client id and secret  
            if self.client_id and self.client_secret: 
                self.plaid_api = PlaidAPI(self.client_id, self.client_secret) 
                return await self.async_step_authorization() 
        
        # We need to get the client_id and client_secret from the user  
        if user_input is not None: 
            self.client_id = user_input.get("client_id", "").strip()
            self.client_secret = user_input.get("client_secret", "").strip()

            self.plaid_api = PlaidAPI(self.client_id, self.client_secret) 
            if not self.client_id or not self.client_secret:
                _LOGGER.error("Client ID or Secret is empty!")
                return self.async_show_form(
                    step_id="user",
                    data_schema=STEP_USER_DATA_SCHEMA,
                    errors={"base": "missing_credentials"}
                )

            return await self.async_step_authorization() 

        return self.async_show_form(
            step_id="user", 
            data_schema=vol.Schema({
                vol.Required("client_id"): str, 
                vol.Required("client_secret"): str   
            })
        )
        
    async def async_step_authorization(self, user_input=None):   
        """Step 2: Show the authorization URL and wait for user to proceed."""

        if user_input is not None:
            # Move to Step 3 (Account Selection)
            return await self.async_step_accounts()

        hosted_link, link_token = await self.plaid_api.get_link_token() 
        if not hosted_link or not link_token: 
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_USER_DATA_SCHEMA,
                errors={"base": "invalid_credentials"}
            )
        
        self.context["link_token"] = link_token  # Save the link token for later     
        return self.async_show_form(
            step_id="authorization",
            data_schema=vol.Schema({}),
            description_placeholders={"hosted_link": hosted_link}
        )

    async def async_step_accounts(self, user_input=None):
        """ Step 3: Exchange token, fetch all accounts, and finish setup. """

        # Step 1: Exchange `link_token` for a `public_token`
        link_session = await self.plaid_api.get_link_session(self.context["link_token"]) 
        if not link_session:
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_USER_DATA_SCHEMA,
                errors={"base": "invalid_link_token"}
            ) 
        
        # Step 2: Exchange `public_token` for an `access_token`
        access_token = await self.plaid_api.exchange_public_token(link_session)
        if not access_token: 
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_USER_DATA_SCHEMA,
                errors={"base": "invalid_public_token"}
            ) 
        
        # Ensure we can get the accounts, along with the institution name  
        accounts, institution = await self.plaid_api.get_accounts(access_token) 
        if not accounts: 
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_USER_DATA_SCHEMA,
                errors={"base": "invalid_access_token"}
            ) 

        return self.async_create_entry(
            title=f"Plaid Integration - {institution}",
            data={
                "client_id": self.client_id, 
                "client_secret": self.client_secret, 
                "access_token": access_token
            }
        )
        
      