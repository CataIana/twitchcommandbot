from disnake.errors import Forbidden
from disnake.ext import commands
from traceback import format_exc, format_exception
from twitchcommandbot.subclasses.custom_context import ApplicationCustomContext
from twitchcommandbot.exceptions import NoPermissions, NotConnected, AlreadyConnected, NotFound, TokenExpired
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from main import TwitchCommandBot

class ErrorListener(commands.Cog):
    def __init__(self, bot):
        self.bot: TwitchCommandBot = bot
        super().__init__()

    @commands.Cog.listener()
    async def on_slash_command_error(self, ctx: ApplicationCustomContext, exception):
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
        await ctx.send(err_msg)

        exc = ''.join(format_exception(type(exception), exception, exception.__traceback__))
        self.bot.log.error(f"Ignoring exception in command {ctx.application_command.name}:\n{exc}")

def setup(bot):
    bot.add_cog(ErrorListener(bot))