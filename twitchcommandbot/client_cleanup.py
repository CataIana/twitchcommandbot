from disnake.ext import tasks, commands
from time import time
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from main import TwitchCommandBot

class ClientCleanup(commands.Cog):
    def __init__(self, bot):
        self.bot: TwitchCommandBot = bot
        self.cleanup.start()

    def cog_unload(self):
        self.cleanup.cancel()

    @tasks.loop(minutes=1)
    async def cleanup(self):
        await self.bot.wait_until_ready()
        self.bot.log.debug("Running client cleanup")
        for guild in list(self.bot.irc_clients.values()):
            for client in list(guild.values()):
                # If client inactive for more than 1 hour
                if (client.last_activity + 3600) < time():
                    self.bot.log.info(f"Closing client \"{client.user.username}\" in {client.guild} due to inactivity")
                    await client.close()

def setup(bot):
    bot.add_cog(ClientCleanup(bot))