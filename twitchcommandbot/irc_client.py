from disnake import Guild
from disnake.ext import commands
from websockets import client
from websockets.exceptions import ConnectionClosed
from .exceptions import NotConnected, AlreadyConnected
import asyncio
from time import time
from twitchcommandbot.user import User
from typing import TYPE_CHECKING, List
if TYPE_CHECKING:
    from main import TwitchCommandBot

class TwitchIRC(commands.Cog):
    __host = "wss://irc-ws.chat.twitch.tv"
    __port = 443

    def __init__(self, bot, guild: Guild, user: User, oauth: str, connected_channels: List[User]):
        self.bot: TwitchCommandBot = bot
        self.loop: asyncio.AbstractEventLoop = bot.loop
        self._ready = asyncio.Event()
        self.__guild = guild
        self.__user = user
        self.__oauth = f"oauth:{oauth.split('oauth:')[-1]}"
        self.__connected_channels = connected_channels
        self.__tasks = []
        self.last_activity = time()

    @property
    def user(self) -> User:
        return self.__user

    @property
    def guild(self) -> Guild:
        return self.__guild

    @property
    def oauth(self) -> str:
        return self.__oauth

    @property
    def closed(self) -> bool:
        return self.__socket.closed

    @property
    def channels(self) -> List[User]:
        return self.__connected_channels

    async def kill_tasks(self):
        [task.cancel() for task in self.__tasks if task is not asyncio.tasks.current_task()]

    async def wait_until_ready(self):
        await self._ready.wait()

    async def message_reciever(self):
        while not self.__socket.closed and not self.bot._closed:
            try:
                message = await self.__socket.recv()
                stripped_message = message.rstrip("\n")
                #self.bot.log.info(f"{self.__guild.name} ({self.__user.username}): {stripped_message}")
                if stripped_message.startswith("PING"):
                    self.bot.log.info(f"{self.__guild.name} ({self.__user.username}): Pong")
                    await self.__socket.send("PONG :tmi.twitch.tv\n")
                    continue
                
                if stripped_message.split(' ')[1] == "001":
                    self.bot.dispatch("irc_connect", self.user)
                elif stripped_message.split(' ')[1] == "JOIN":
                    self.bot.dispatch("irc_join", self.user, stripped_message.split(' ')[-1].lstrip("#"))
                elif stripped_message.split(' ')[1] == "PART":
                    self.bot.dispatch("irc_part", self.user, stripped_message.split(' ')[-1].lstrip("#"))
            except ConnectionClosed:
                await self.kill_tasks()

    async def join(self, channel: User):
        def check(u, c):
            return c == channel and u == self.user
        await self.wait_until_ready()
        self.last_activity = time()
        if channel not in self.__connected_channels:
            await self.__socket.send(f"JOIN #{channel}\n")
            await self.bot.wait_for("irc_join", check=check, timeout=8)
            self.__connected_channels.append(channel)
        else:
            raise AlreadyConnected(channel)

    async def part(self, channel: User):
        def check(u, c):
            return c == channel and u == self.user
        await self.wait_until_ready()
        self.last_activity = time()
        if channel in self.__connected_channels:
            await self.__socket.send(f"PART #{channel}\n")
            await self.bot.wait_for("irc_part", check=check, timeout=8)
            self.__connected_channels.remove(channel)
        else:
            raise NotConnected(channel)

    async def send(self, channel: User, message: str):
        await self.wait_until_ready()
        self.last_activity = time()
        if channel not in self.__connected_channels:
            raise NotConnected(channel)
        await self.__socket.send(f"PRIVMSG #{channel.username} :{message}")

    async def connect(self):
        failed_attempts = 0
        while not self.bot._closed:  # Not sure if it works, but an attempt at a connecting backoff
            self.__socket = await client.connect(f"{self.__host}:{self.__port}")
            if self.__socket.closed:
                if 2**failed_attempts > 128:
                    await asyncio.sleep(120)
                else:
                    await asyncio.sleep(2**failed_attempts)
                failed_attempts += 1 # Continue to back off exponentially with every failed connection attempt up to 2 minutes
                self.bot.log.info(f"{self.__guild.name} ({self.__user.username}): {failed_attempts} failed attempts to connect.")
            else:
                break
        self.bot.log.info(f"{self.__guild.name} ({self.__user.username}): Connected to websocket")
        await self.__socket.send(f"PASS {self.__oauth}\n")
        await self.__socket.send(f"NICK {self.__user.username}\n")

        self.__tasks = [
            self.loop.create_task(self.message_reciever())
        ]
        def connect_check(u):
            return u == self.user
        await self.bot.wait_for("irc_connect", check=connect_check, timeout=8)

        for channel in self.__connected_channels:
            def check(u, c):
                return u == self.user, c == channel
            await self.__socket.send(f"JOIN #{channel.username}\n")
            await self.bot.wait_for("irc_join", check=check, timeout=8)
            await asyncio.sleep(1)
        self.bot.log.info(f"{self.__guild.name} ({self.__user.username}): Joined channels ({', '.join([c.name for c in self.__connected_channels])})")
        self._ready.set()
        # try:
        #     await asyncio.wait(self.__tasks) # Tasks will run until the connection closes, we need to re-establish it if it closes
        # except asyncio.exceptions.CancelledError:
        #     pass
    
    async def close(self):
        await self.wait_until_ready()
        del self.bot.irc_clients[self.__guild][self.__user.username]
        self._ready.clear()
        if not self.__socket.closed:
            self.bot.log.info(f"{self.__guild.name} ({self.__user.username}): Disconnecting from websocket")
            await self.__socket.close()
