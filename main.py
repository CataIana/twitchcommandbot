from __future__ import annotations
import disnake
from disnake.ext import commands
from aiohttp import ClientSession
from time import time
import logging
import json
import sys
import asyncio
from twitchcommandbot.exceptions import TokenExpired
from twitchcommandbot.subclasses import CustomConnectionState
from twitchcommandbot import TwitchIRC, http, User, NotFound
import aiofiles
from typing import TypeVar, Type, Any, Dict

ACXT = TypeVar("ACXT", bound="disnake.ApplicationCommandInteraction")
class TwitchCommandBot(commands.InteractionBot):
    from twitchcommandbot.subclasses import _sync_application_commands

    def __init__(self):
        intents = disnake.Intents.none()
        intents.guilds = True

        with open("config.json") as f:
            self.auth = json.load(f)
        super().__init__(intents=intents, owner_ids=self.auth.get("bot_owners", []))
        self._sync_commands_debug = True

        self.log: logging.Logger = logging.getLogger("TwitchCommandBot")
        self.log.setLevel(logging.INFO)

        shandler = logging.StreamHandler(sys.stdout)
        shandler.setLevel(self.log.level)
        shandler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
        self.log.addHandler(shandler)

        self.robot_heartbeat_url = self.auth.get("uptime_heartbeat_url", None)
        try:
            self.robot_heartbeat_frequency = int(self.auth.get("uptime_heartbeat_frequency_every_x_minutes", 0))
        except ValueError:
            raise ValueError("Uptime heartbeat frequency is not a valid integer!")
        self.colour = disnake.Colour.from_rgb(128, 0, 128)
        self.token = self.auth["discord_bot_token"]
        self.twitch_client_id = self.auth["twitch_client_id"]
        self.twitch_client_secret = self.auth["twitch_client_secret"]
        self.api = http(self, "config.json")
        self._uptime = time()
        self.load_extension(f"twitchcommandbot.etc_commands")
        self.load_extension(f"twitchcommandbot.commands")
        self.load_extension(f"twitchcommandbot.exception_listener")
        #self.load_extension(f"twitchcommandbot.client_cleanup")
        self.load_extension(f"twitchcommandbot.token_maintainer")

        self.irc_clients: Dict[disnake.Guild, Dict[str, TwitchIRC]] = {}
        self.application_invoke = self.process_application_commands
        self.loop.create_task(self.robot_heartbeat())

    async def close(self):
        self.log.info("Shutting down...")
        for d in dict(self.irc_clients).values():
            for client in list(d.values()):
                if not client.closed:
                    await client.close()
        if not self.aSession.closed:
            await self.aSession.close()
        await super().close()

    @commands.Cog.listener()
    async def on_connect(self):
        self.aSession: ClientSession = ClientSession() #Make the aiohttp session asap
        await self.start_all_clients()

    @commands.Cog.listener()
    async def on_ready(self):
        self.log.info(f"------ Logged in as {self.user.name} - {self.user.id} ------")
        self.log.info(f"Invite URL: https://discord.com/oauth2/authorize?client_id={self.user.id}&permissions=3072&scope=applications.commands+bot")

    def _get_state(self, **options: Any) -> CustomConnectionState:
        return CustomConnectionState(
            dispatch=self.dispatch,
            handlers=self._handlers,
            hooks=self._hooks,
            http=self.http,
            loop=self.loop,
            **options,
        )

    async def on_application_command(self, interaction): return

    async def get_slash_context(self, interaction: disnake.Interaction, *, cls: Type[ACXT] = disnake.ApplicationCommandInteraction):
        return cls(data=interaction, state=self._connection)

    async def get_irc_client(self, guild: disnake.Guild, user: User, create_new: bool = True) -> TwitchIRC:
        # Attempt to fetch existing client for guild
        if create_new and self.irc_clients.get(guild, None) is None:
            self.irc_clients[guild] = {}
        client = self.irc_clients.get(guild, {}).get(user.username, None)
        # Create a new client if not found
        if not client and not create_new:
            raise NotFound
        elif client is None and create_new:
            try:
                async with aiofiles.open("connections.json") as f:
                    connections = json.loads(await f.read())
            except FileNotFoundError:
                connections = {}
            except json.decoder.JSONDecodeError:
                connections = {}

            data = connections.get(str(guild.id), {}).get(str(user.id), None)
            if data is None: # If it wasn't found, assume the user has not been setup
                raise commands.UserNotFound("User has not been setup!")
            
            # Updated cached username if different
            if user.username != connections[str(guild.id)][str(user.id)]["username"]:
                connections[str(guild.id)][str(user.id)]["username"] = user.username
                async with aiofiles.open("connections.json", "w") as f:
                    await f.write(json.dumps(connections, indent=4))

            token = connections[str(guild.id)][str(user.id)]["access_token"]
            if await self.api.validate_token(user, token, required_scopes=["chat:read", "chat:edit"]) == False:
                raise TokenExpired(f"Token has expired for client {user.username}! Please update the token")

            channels = await self.api.get_users(user_ids=connections[str(guild.id)][str(user.id)]["joined_channels"])
            # Create new client with provided data
            client = TwitchIRC(self, guild, user, token, channels)
            await client.connect()
            self.irc_clients[guild][user.username] = client
        return client

    async def robot_heartbeat(self):
        await self.wait_until_ready()
        while not self.is_closed():
            if self.robot_heartbeat_url and self.robot_heartbeat_frequency > 0:
                self.log.debug("Sending uptime heartbeat")
                await self.aSession.get(self.robot_heartbeat_url)
            # Sleep for defined value
            await asyncio.sleep(self.robot_heartbeat_frequency*60)

    async def start_all_clients(self):
        self.log.info("Starting IRC Clients. This may take some time")
        try:
            async with aiofiles.open("connections.json") as f:
                connections = json.loads(await f.read())
        except FileNotFoundError:
            connections = {}
        except json.decoder.JSONDecodeError:
            connections = {}
        for guild_id, guild_data in connections.items():
            guild = self.get_guild(int(guild_id))
            if guild:
                for user_id, user_data in guild_data.items():
                    try:
                        int(user_id)
                    except ValueError:
                        continue
                    user = await self.api.get_user(user_id=user_id)
                    try:
                        await self.api.validate_token(user, user_data["access_token"], required_scopes=["chat:read", "chat:edit"])
                    except TokenExpired:
                        expiry_channel = connections[str(guild.id)].get("expiry_channel", None)
                        if expiry_channel:
                            ex = self.get_channel(expiry_channel)
                            try:
                                await ex.send(f"Token for client {user.username} has expired! Please update the token")
                            except disnake.Forbidden:
                                pass
                            except disnake.HTTPException:
                                pass
                    else:
                        await self.get_irc_client(guild, user)
                    await asyncio.sleep(2)
        self.log.info("Finished starting IRC clients")
    

if __name__ == "__main__":
    bot = TwitchCommandBot()
    bot.run(bot.token)
