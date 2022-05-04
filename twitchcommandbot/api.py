from __future__ import annotations
from typing import TYPE_CHECKING
import aiofiles
import json
from disnake import HTTPException
from aiohttp import ClientSession
from .user import PartialUser, User
from .exceptions import BadAuthorization, BadRequest, NotFound
from typing import Union, List, Dict
if TYPE_CHECKING:
    from main import TwitchCommandBot

class http:
    def __init__(self, bot, auth_file):
        self.bot: TwitchCommandBot = bot
        self.base = "https://api.twitch.tv/helix"
        self.oauth2_base = "https://id.twitch.tv/oauth2"
        self.storage = auth_file
        try:
            with open(auth_file) as f:
                a = json.load(f)
        except FileNotFoundError:
            raise BadAuthorization
        except json.decoder.JSONDecodeError:
            raise BadAuthorization
        try:
            self.client_id = a["twitch_client_id"]
            self.client_secret = a["twitch_client_secret"]
            self.access_token = a.get("twitch_access_token", "")
        except KeyError:
            raise BadAuthorization
        self.bot.add_listener(self._make_session, 'on_connect')

    @property
    def headers(self) -> Dict:
        return {"Authorization": f"Bearer {self.access_token}", "Client-Id": self.client_id}

    async def _make_session(self):
        self.session: ClientSession = ClientSession()

    async def _request(self, url, method="get", **kwargs):
        response = await self.session.request(method=method, url=url, headers=self.headers, **kwargs)
        if response.status == 401: #Refresh access token
            reauth = await self.session.post(
                url=f"{self.oauth2_base}/token", data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "grant_type": "client_credentials"
            })
            if reauth.status in [401, 400]:
                reauth_data = await reauth.json()
                raise BadAuthorization(reauth_data["message"])
            reauth_data = await reauth.json()
            async with aiofiles.open(self.storage) as f:
                self.bot.auth = json.loads(await f.read())
            self.bot.auth["access_token"] = reauth_data["access_token"]
            async with aiofiles.open(self.storage, "w") as f:
                await f.write(json.dumps(self.bot.auth, indent=4))
            self.access_token = reauth_data['access_token']
            response = await self.session.request(method=method, url=url, headers=self.headers, **kwargs)
        return response

    def chunks(self, lst, n):
        """Yield successive n-sized chunks from lst."""
        for i in range(0, len(lst), n):
            yield lst[i:i + n]

    async def get_users(self, users: List[PartialUser] = [], user_ids: List[int] = [], user_logins: List[str] = []) -> List[User]:
        queries = []
        queries += [f"id={user.id}" for user in users]
        queries += [f"id={id}" for id in user_ids]
        queries += [f"login={login}" for login in user_logins]
        users = []
        for chunk in self.chunks(queries, 100):
            join = '&'.join(chunk)
            r = await self._request(f"{self.base}/users?{join}")
            if r.status != 200:
                rj = await r.json()
                raise HTTPException(r, rj["message"])
            json_data = (await r.json())["data"]
            for user_json in json_data:
                users += [User(**user_json)]
        return users

    async def get_user(self, user: PartialUser = None, user_id: int = None, user_login: str = None) -> Union[User, None]:
        if user is not None:
            r = await self._request(f"{self.base}/users?id={user.id}")
        elif user_id is not None:
            r = await self._request(f"{self.base}/users?id={user_id}")
        elif user_login is not None:
            r = await self._request(f"{self.base}/users?login={user_login}")
        else:
            raise BadRequest
        j = await r.json()
        if r.status != 200:
            raise HTTPException(r, j["message"])
        if j["data"] == []:
            raise NotFound("User not found!")
        json_data = j["data"][0]
        return User(**json_data)

    async def validate_token(self, user: User, token: str, required_scopes: List[str] = None):
        stripped_token = token.split("oauth:")[-1]
        r = await self.session.get(f"https://id.twitch.tv/oauth2/validate", headers={"Authorization": f"Bearer {stripped_token}"})
        if r.status == 200:
            rj = await r.json()
            if rj["login"] != user.username:
                return False
            if required_scopes:
                for scope in required_scopes:
                    if scope not in rj["scopes"]:
                        return False
            return True
        elif r.status == 401:
            return False
        return None
