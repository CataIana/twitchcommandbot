from disnake.ext import tasks, commands
from datetime import time, datetime
import asyncio
from typing import TYPE_CHECKING
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

    @tasks.loop(time=time(hour=0))
    async def maintainer(self):
        await self.bot.wait_until_ready()
        self.bot.log.info("Restarting clients")
        for d in dict(self.bot.irc_clients).values():
            for client in list(d.values()):
                if not client.closed:
                    await client.close()
        await asyncio.sleep(2)
        await self.bot.start_all_clients()

def setup(bot):
    bot.add_cog(TokenMaintainer(bot))