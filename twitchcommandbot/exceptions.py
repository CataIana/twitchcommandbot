from disnake.ext import commands
from twitchcommandbot.user import User


class TwitchCommandBotException(commands.CommandError):
    pass

class BadAuthorization(TwitchCommandBotException):
    def __init__(self):
        super().__init__("Bad authorization! Please check your configuration.")

class BadRequest(TwitchCommandBotException):
    pass

class NotConnected(TwitchCommandBotException):
    def __init__(self, channel: User):
        super().__init__(f"Not connected to channel \"{channel.username}\"!")

class AlreadyConnected(TwitchCommandBotException):
    def __init__(self, channel: User):
        super().__init__(f"Already connected to channel \"{channel.username}\"!")

class NotFound(TwitchCommandBotException):
    def __init__(self, message: str = None):
        super().__init__(message)

class NoPermissions(TwitchCommandBotException):
    def __init__(self):
        super().__init__("You do not have permissions use this command")

class TokenExpired(TwitchCommandBotException):
    def __init__(self, message: str):
        super().__init__(message or "The token for this account has expired")