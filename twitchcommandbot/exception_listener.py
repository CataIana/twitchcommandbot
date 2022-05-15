from disnake.errors import Forbidden, HTTPException
from disnake.ext import commands
from traceback import format_exception
from twitchcommandbot.subclasses.custom_context import ApplicationCustomContext
from twitchcommandbot.exceptions import NoPermissions, NotConnected, AlreadyConnected, NotFound, TokenExpired
import aiofiles
import json
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from main import TwitchCommandBot

class ErrorListener(commands.Cog):
    def __init__(self, bot):
        self.bot: TwitchCommandBot = bot
        super().__init__()

    @commands.Cog.listener()
    async def on_slash_command_error(self, ctx: ApplicationCustomContext, exception):
        if isinstance(exception, TokenExpired):
            try:
                async with aiofiles.open("connections.json") as f:
                    connections = json.loads(await f.read())
            except FileNotFoundError:
                connections = {}
            except json.decoder.JSONDecodeError:
                connections = {}
            if not connections[str(exception.guild.id)][str(exception.user.id)].get("expiry_notified", False):
                connections[str(exception.guild.id)][str(exception.user.id)]["expiry_notified"] = True
                async with aiofiles.open("connections.json", "w") as f:
                    await f.write(json.dumps(connections, indent=4))
                expiry_channel = connections[str(exception.guild.id)].get("expiry_channel", None)
                if expiry_channel:
                    ex = self.bot.get_channel(expiry_channel)
                    try:
                        await ex.send(f"Token for client {exception.user.username} has expired! Please update the token")
                    except Forbidden:
                        pass
                    except HTTPException:
                        pass

        if isinstance(exception, (commands.MissingPermissions, commands.NotOwner, commands.MissingRole, commands.CheckFailure, 
                                    commands.BadArgument, AlreadyConnected, NotConnected, NotFound, commands.UserNotFound, 
                                    commands.BadArgument, NoPermissions, TokenExpired)):
            return await ctx.send(f"{exception}")
        if isinstance(exception, Forbidden):
            return await ctx.send("The bot does not have access to send messages!")

        if await self.bot.is_owner(ctx.author):
            err_msg = f"There was an error executing this command.\n`{type(exception).__name__}: {exception}`"
        else:
            err_msg = f"There was an error executing this command."
        await ctx.send(err_msg, ephemeral=True)

        exc = ''.join(format_exception(type(exception), exception, exception.__traceback__))
        self.bot.log.error(f"Ignoring exception in command {ctx.application_command.name}:\n{exc}")

def setup(bot):
    bot.add_cog(ErrorListener(bot))