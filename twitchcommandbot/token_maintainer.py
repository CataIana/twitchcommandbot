from disnake import Forbidden, HTTPException
from disnake.ext import tasks, commands
from datetime import time, datetime
import asyncio
import aiofiles
import json
from typing import TYPE_CHECKING

from twitchcommandbot.exceptions import TokenExpired
if TYPE_CHECKING:
    from main import TwitchCommandBot

class TokenMaintainer(commands.Cog):
    def __init__(self, bot):
        self.bot: TwitchCommandBot = bot
        self.index = 0
        self.maintainer.start()
        #self.bot.loop.create_task(self.maintainer())

    def cog_unload(self):
        self.maintainer.cancel()

    @tasks.loop(time=time(hour=0, tzinfo=datetime.now().astimezone().tzinfo))
    async def maintainer(self):
        await self.bot.wait_until_ready()
        self.bot.log.info("Running client token refresh")
        try:
            async with aiofiles.open("connections.json") as f:
                connections = json.loads(await f.read())
        except FileNotFoundError:
            connections = {}
        except json.decoder.JSONDecodeError:
            connections = {}
        for guild_id, guild_data in connections.items():
            guild = self.bot.get_guild(int(guild_id))
            if guild:
                for user_id, user_data in guild_data.items():
                    try:
                        int(user_id)
                    except ValueError:
                        continue
                    user = await self.bot.api.get_user(user_id=user_id)
                    try:
                        await self.bot.api.validate_token(user, user_data["access_token"], required_scopes=["chat:read", "chat:edit"])
                    except TokenExpired:
                        expiry_channel = connections[str(guild.id)].get("expiry_channel", None)
                        if expiry_channel:
                            ex = self.bot.get_channel(expiry_channel)
                            try:
                                await ex.send(f"Token for client {user.username} has expired! Please update the token")
                            except Forbidden:
                                pass
                            except HTTPException:
                                pass
                    await asyncio.sleep(60)
        self.bot.log.info("Finished client token refresh")

def setup(bot):
    bot.add_cog(TokenMaintainer(bot))