import logging
import aiohttp 
_LOGGER = logging.getLogger(__name__)

class PlaidAPI:
    def __init__(self, client_id, client_secret):
        self.client_id = client_id
        self.client_secret = client_secret
        self.base_url = "https://production.plaid.com"

    async def get_link_token(self): 
        try: 
            """Create a link token to add a new account."""
            url = f"{self.base_url}/link/token/create"
            payload = {
                "client_id": self.client_id,
                "secret": self.client_secret, 
                "client_name": "Home Assistant", 
                "language": "en", 
                "products": ["transactions"], 
                "country_codes": ["US"], 
                "user": {
                    "client_user_id": "home-assistant-user" 
                }, 
                "hosted_link": {}, 
            }

            async with aiohttp.ClientSession() as session: 
                async with session.post(url, json=payload) as response: 
                    if(response.status != 200): 
                        return None, None 

                    data = await response.json() 
                    hosted_link = data.get('hosted_link_url')
                    link_token = data.get('link_token')

                    return hosted_link, link_token 


            return None, None    
        except Exception as e: 
            _LOGGER.error(f"Failed to create link token: {e}")
            return None, None 

    async def get_link_session(self, link_token): 
        try:
            payload = {
                "client_id": self.client_id,
                "secret": self.client_secret, 
                "link_token": link_token
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(f"{self.base_url}/link/token/get", json=payload) as response: 
                    if(response.status != 200): 
                        return None

                    data = await response.json() 
                    link_session = None 
                    for s in data.get("link_sessions", []): 
                        results = s.get("results", {}) 
                        item_add_results = results.get("item_add_results", []) 
                        item = next((i for i in item_add_results if "public_token" in i), None) 
                        if item: 
                            link_session = s 
                            link_session["public_token"] = item["public_token"] 
                            break 

                    if not link_session:
                        _LOGGER.error("Plaid API response missing link_session")
                        return None
                    
                    return link_session
        except Exception as e: 
            _LOGGER.error(f"Failed to create link session: {e}")
            return None

    async def exchange_public_token(self, link_session): 
        try: 
            # Parse the public token from the link session.  
            public_token = link_session.get("public_token") 
            if not public_token: 
                _LOGGER.error("Plaid API response missing public_token")
                return None 
            
            # Exchange the public token for an access token. 
            async with aiohttp.ClientSession() as session: 
                async with session.post(f"{self.base_url}/item/public_token/exchange", json={
                    "client_id": self.client_id, 
                    "secret": self.client_secret, 
                    "public_token": public_token
                }) as response: 
                    if(response.status != 200): 
                        return None 

                    data = await response.json() 
                    access_token = data.get("access_token")
                    return access_token 
        except: 
            return None 
        
    async def get_accounts(self, access_token):
        try: 
            """Retrieve account balances from Plaid."""
            url = f"{self.base_url}/accounts/get"
            payload = {
                "client_id": self.client_id,
                "secret": self.client_secret,
                "access_token": access_token
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as response:
                    if response.status != 200:
                        error_msg = await response.text()
                        _LOGGER.error("Plaid API request failed: %s", error_msg)
                        return None, None

                    data = await response.json() 
                    accounts = data.get("accounts", [])
                    instution = data.get("item", {}).get("institution_name") 
                    return accounts, instution
        except Exception as e:
            _LOGGER.error(f"Failed to fetch accounts: {e}")
            return None, None
