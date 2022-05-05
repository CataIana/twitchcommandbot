from disnake import Member, TextChannel
from disnake.ext import commands
from twitchcommandbot.subclasses import ApplicationCustomContext
from twitchcommandbot import NotFound, NotConnected, NoPermissions
import aiofiles
import json
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from main import TwitchCommandBot

class IRCCommands(commands.Cog):
    def __init__(self, bot):
        self.bot: TwitchCommandBot = bot
        super().__init__()

    async def channel_autocomplete(ctx: ApplicationCustomContext, user_input: str):
        self = ctx.application_command.cog
        try:
            async with aiofiles.open("connections.json") as f:
                connections = json.loads(await f.read())
        except FileNotFoundError:
            connections = {}
        except json.decoder.JSONDecodeError:
            connections = {}
        usernames = [user.username for user in await self.bot.api.get_users(user_ids=[k for k in connections.get(str(ctx.guild.id), {}).keys() if k != "expiry_channel"])]
        return [channel for channel in usernames if channel.startswith(user_input)][:25]

    async def joined_channels_autocomplete(ctx: ApplicationCustomContext, user_input: str):
        self = ctx.application_command.cog
        try:
            async with aiofiles.open("connections.json") as f:
                connections = json.loads(await f.read())
        except FileNotFoundError:
            connections = {}
        except json.decoder.JSONDecodeError:
            connections = {}
        user_obj = await self.bot.api.get_user(user_login=ctx.filled_options["user"])
        if user_obj is None:
            return ["No such channel with this name!"]
        return [channel.username for channel in await self.bot.api.get_users(user_ids=connections[str(ctx.guild.id)][str(user_obj.id)]["joined_channels"]) if channel.username.startswith(user_input)][:25]

    async def group_autocomplete(ctx: ApplicationCustomContext, user_input: str):
        self = ctx.application_command.cog
        try:
            async with aiofiles.open("groups.json") as f:
                groups = json.loads(await f.read())
        except FileNotFoundError:
            groups = {}
        except json.decoder.JSONDecodeError:
            groups = {}
        return [group for group in groups.get(str(ctx.guild.id), {}).keys() if group.startswith(user_input)][:25]

    async def channel_group_autocomplete(ctx: ApplicationCustomContext, user_input: str):
        self = ctx.application_command.cog
        try:
            async with aiofiles.open("groups.json") as f:
                groups = json.loads(await f.read())
        except FileNotFoundError:
            groups = {}
        except json.decoder.JSONDecodeError:
            groups = {}
        group_name = ctx.filled_options["group_name"]
        usernames = [user.username for user in await self.bot.api.get_users(user_ids=groups.get(str(ctx.guild.id), {}).get(group_name, []))]
        return [channel for channel in usernames if channel.startswith(user_input)][:25]

    def has_permissions():
        async def predicate(ctx: ApplicationCustomContext) -> bool:
            try:
                async with aiofiles.open("permissions.json") as f:
                    permissions = json.loads(await f.read())
            except FileNotFoundError:
                permissions = {}
            except json.decoder.JSONDecodeError:
                permissions = {}
            try:
                async with aiofiles.open("config.json") as f:
                    auth = json.loads(await f.read())
            except FileNotFoundError:
                auth = {}
            except json.decoder.JSONDecodeError:
                auth = {}
            if ctx.author.guild_permissions.administrator:
                return True
            if ctx.author.id in permissions.get(str(ctx.guild.id), []):
                return True
            if ctx.author.id in auth.get("bot_owners", []):
                return True
            raise NoPermissions
        return commands.check(predicate)

    @commands.slash_command()
    @has_permissions()
    async def client(self, ctx: ApplicationCustomContext):
        pass

    @client.sub_command(name="new", description="Add a new twitch client")
    async def client_new(self, ctx: ApplicationCustomContext, username: str, oauth_token: str = commands.Param(description="Ensure this oauth token has chat access (chat:read, chat:edit)")):
        try:
            user = await self.bot.api.get_user(user_login=username)
        except NotFound:
            return await ctx.send("User does not exist!", ephemeral=True)

        try:
            await self.bot.get_irc_client(ctx.guild, user)
        except commands.UserNotFound:
            pass
        else:
            return await ctx.send("User has already been setup!", ephemeral=True)

        if await self.bot.api.validate_token(user, oauth_token, required_scopes=["chat:read", "chat:edit"]) == False:
            return await ctx.send("Provided token is not valid, does not match the provided username, or does not contain the required scopes!", ephemeral=True)

        try:
            async with aiofiles.open("connections.json") as f:
                connections = json.loads(await f.read())
        except FileNotFoundError:
            connections = {}
        except json.decoder.JSONDecodeError:
            connections = {}

        if not connections.get(str(ctx.guild.id), None):
            connections[str(ctx.guild.id)] = {}

        connections[str(ctx.guild.id)][str(user.id)] = {"username": username, "access_token": oauth_token, "joined_channels": [user.id]}
        async with aiofiles.open("connections.json", "w") as f:
            await f.write(json.dumps(connections, indent=4))
        self.bot.loop.create_task(self.bot.get_irc_client(ctx.guild, user))
        self.bot.log.info(f"Added new client \"{username}\" to guild {ctx.guild}")
        await ctx.send("Client successfully added!", ephemeral=True)

    @client.sub_command(name="remove", description="Remove a twitch client")
    async def client_remove(self, ctx: ApplicationCustomContext, username: str = commands.Param(autocomplete=channel_autocomplete)):
        try:
            user = await self.bot.api.get_user(user_login=username)
        except NotFound:
            return await ctx.send("User does not exist!", ephemeral=True)

        try:
            client = await self.bot.get_irc_client(ctx.guild, user, create_new=False)
            await client.close()
        except NotFound:
            pass

        try:
            async with aiofiles.open("connections.json") as f:
                connections = json.loads(await f.read())
        except FileNotFoundError:
            connections = {}
        except json.decoder.JSONDecodeError:
            connections = {}
        try:
            del connections[str(ctx.guild.id)][str(user.id)]
        except KeyError:
            return await ctx.send("User not setup with bot!", ephemeral=True)
        if connections[str(ctx.guild.id)] == {}:
            del connections[str(ctx.guild.id)]

        async with aiofiles.open("connections.json", "w") as f:
            await f.write(json.dumps(connections, indent=4))
        self.bot.log.info(f"Deleted client \"{username}\" from guild {ctx.guild}")
        await ctx.send("Client successfully removed!")

    @client.sub_command(name="update", description="Update an existing twitch client")
    async def client_update(self, ctx: ApplicationCustomContext, username: str = commands.Param(autocomplete=channel_autocomplete), oauth_token: str = commands.Param(description="Ensure this oauth token has chat access (chat:read, chat:edit)")):
        try:
            user = await self.bot.api.get_user(user_login=username)
        except NotFound:
            return await ctx.send("User does not exist!", ephemeral=True)

        try:
            async with aiofiles.open("connections.json") as f:
                connections = json.loads(await f.read())
        except FileNotFoundError:
            connections = {}
        except json.decoder.JSONDecodeError:
            connections = {}

        if str(user.id) not in connections[str(ctx.guild.id)].values():
            return await ctx.send("User not setup with bot!", ephemeral=True)

        try:
            client = await self.bot.get_irc_client(ctx.guild, user)
            await client.close()
        except commands.UserNotFound:
            pass
        except NotFound:
            pass

        if await self.bot.api.validate_token(user, oauth_token, required_scopes=["chat:read", "chat:edit"]) == False:
            return await ctx.send("Provided token is not valid, does not match the provided username, or does not contain the required scopes!", ephemeral=True)

        connections[str(ctx.guild.id)][str(user.id)]["access_token"] = oauth_token
        async with aiofiles.open("connections.json", "w") as f:
            await f.write(json.dumps(connections, indent=4))
        self.bot.log.info(f"Updated client \"{username}\" in guild {ctx.guild}")
        await ctx.send("Client successfully updated!", ephemeral=True)

    @client.sub_command(name="list", description="List all setup clients in the server")
    async def client_list(self, ctx: ApplicationCustomContext):
        try:
            async with aiofiles.open("connections.json") as f:
                connections = json.loads(await f.read())
        except FileNotFoundError:
            connections = {}
        except json.decoder.JSONDecodeError:
            connections = {}

        if connections.get(str(ctx.guild.id), None) is None:
            return await ctx.send("No clients have been setup in this server!")

        users = await self.bot.api.get_users(user_ids=[u for u in connections[str(ctx.guild.id)].keys() if u != "expiry_channel"])
        await ctx.send(f"There are currently {len(users)} client{'s' if len(users) != 1 else ''} setup in this server:\n**Clients:** {', '.join([user.username for user in users])}", ephemeral=True)

    # @commands.slash_command(description="Have a client join the provided twitch channel")
    # @has_permissions()
    # async def join(self, ctx: ApplicationCustomContext,
    #                 user: str = commands.Param(description="The authorized user that should be joining a channel", autocomplete=channel_autocomplete),
    #                 channel: str = commands.Param(description="The channel to be joining")):
    #     try:
    #         channel_obj = await self.bot.api.get_user(user_login=channel)
    #     except NotFound:
    #         raise NotFound("Channel not found!")
    #     user_obj = await self.bot.api.get_user(user_login=user)
    #     try:
    #         client = await self.bot.get_irc_client(ctx.guild, user_obj, create_new=False)
    #     except NotFound:
    #         pass
    #     else:
    #         await client.join(channel_obj)
    #     try:
    #         async with aiofiles.open("connections.json") as f:
    #             connections = json.loads(await f.read())
    #     except FileNotFoundError:
    #         connections = {}
    #     except json.decoder.JSONDecodeError:
    #         connections = {}
    #     connections[str(ctx.guild.id)][str(user_obj.id)]["joined_channels"].append(channel_obj.id)
    #     async with aiofiles.open("connections.json", "w") as f:
    #         await f.write(json.dumps(connections, indent=4))
    #     self.bot.log.info(f"\"{user_obj.username}\" joined channel \"{channel_obj.username}\" in guild {ctx.guild}")
    #     await ctx.send(f"Joined channel \"{channel}\"")

    # @commands.slash_command(description="Leave/part a twitch channel")
    # @has_permissions()
    # async def part(self, ctx: ApplicationCustomContext,
    #                 user: str = commands.Param(description="The authorized user that should be leaving a channel", autocomplete=channel_autocomplete),
    #                 channel: str = commands.Param(description="The channel to be leaving", autocomplete=joined_channels_autocomplete)):
    #     try:
    #         channel_obj = await self.bot.api.get_user(user_login=channel)
    #     except NotFound:
    #         raise NotFound("Channel not found!")
    #     user_obj = await self.bot.api.get_user(user_login=user)
    #     try:
    #         client = await self.bot.get_irc_client(ctx.guild, user_obj, create_new=False)
    #     except NotFound:
    #         pass
    #     else:
    #         await client.part(channel_obj)
    #     try:
    #         async with aiofiles.open("connections.json") as f:
    #             connections = json.loads(await f.read())
    #     except FileNotFoundError:
    #         connections = {}
    #     except json.decoder.JSONDecodeError:
    #         connections = {}
    #     connections[str(ctx.guild.id)][str(user_obj.id)]["joined_channels"].remove(channel_obj.id)
    #     async with aiofiles.open("connections.json", "w") as f:
    #         await f.write(json.dumps(connections, indent=4))
    #     self.bot.log.info(f"\"{user_obj.username}\" left channel \"{channel_obj.username}\" in guild {ctx.guild}")
    #     await ctx.send(f"Left channel \"{channel}\"")

    # @commands.slash_command(description="Leave/part a twitch channel")
    # async def connectedchannels(self, ctx: ApplicationCustomContext, user: str = commands.Param(description="The authorized user", autocomplete=channel_autocomplete)):
    #     try:
    #         async with aiofiles.open("connections.json") as f:
    #             connections = json.loads(await f.read())
    #     except FileNotFoundError:
    #         connections = {}
    #     except json.decoder.JSONDecodeError:
    #         connections = {}
    #     user_obj = await self.bot.api.get_user(user_login=user)
    #     if connections.get(str(ctx.guild.id), {}).get(str(user_obj.id), None) is None:
    #         raise commands.BadArgument("User not setup for this server!")
    #     channels = [channel for channel in await self.bot.api.get_users(user_ids=connections[str(ctx.guild.id)][str(user_obj.id)]["joined_channels"])]
    #     await ctx.send(f"User {user_obj.name} is connected to {len(channels)} channel{'s' if len(channels) != 1 else ''}\n**Channels:** {', '.join([c.name for c in channels])}")

    @commands.slash_command()
    @has_permissions()
    async def sendirc(self, ctx: ApplicationCustomContext):
        await ctx.response.defer()

    @sendirc.sub_command(name="all", description="Send a command with all users setup in server")
    async def send_all(self, ctx: ApplicationCustomContext, command: str):
        try:
            async with aiofiles.open("connections.json") as f:
                connections = json.loads(await f.read())
        except FileNotFoundError:
            connections = {}
        except json.decoder.JSONDecodeError:
            connections = {}
        users = [u for u in await self.bot.api.get_users(user_ids=[k for k in connections.get(str(ctx.guild.id), {}).keys() if k != "expiry_channel"])]

        c = 0
        for user in users:
            client = await self.bot.get_irc_client(ctx.guild, user)
            for channel in client.channels:
                await client.send(channel, command)
            c += 1
        self.bot.log.info(f"Sent message with all clients in {ctx.guild}")
        await ctx.send(f"Sent message `{command}` to {c} channel{'s' if c != 1 else ''}")

    @sendirc.sub_command(name="group", description="Send a command in all channels in a specified group")
    async def send_group(self, ctx: ApplicationCustomContext, group_name: str = commands.Param(autocomplete=group_autocomplete), command: str = commands.Param()):
        try:
            async with aiofiles.open("groups.json") as f:
                groups = json.loads(await f.read())
        except FileNotFoundError:
            groups = {}
        except json.decoder.JSONDecodeError:
            groups = {}
        if groups.get(str(ctx.guild.id), None) == None:
            raise commands.BadArgument("Group does not exist!")
        if groups[str(ctx.guild.id)].get(group_name, None) == None:
            raise commands.BadArgument("Group does not exist!")

        users = await self.bot.api.get_users(user_ids=groups[str(ctx.guild.id)][group_name])
        c = 0
        for user in users:
            client = await self.bot.get_irc_client(ctx.guild, user)
            for channel in client.channels:
                await client.send(channel, command)
            c += 1
        self.bot.log.info(f"Sent message to all clients in group {group_name} from {client.user.username} in guild {ctx.guild}")
        await ctx.send(f"Sent message `{command}` to {c} channel{'s' if c != 1 else ''} in group \"{group_name}\"")

    @sendirc.sub_command(name="channel", description="Send a message in a specific channel")
    #async def send_channel(self, ctx: ApplicationCustomContext, user: str = commands.Param(description="The authorized user", autocomplete=channel_autocomplete), channel: str = commands.Param(autocomplete=joined_channels_autocomplete), command: str = commands.Param()):
    async def send_channel(self, ctx: ApplicationCustomContext, user_str: str = commands.Param(description="The authorized user", autocomplete=channel_autocomplete, name="user"), command: str = commands.Param()):
        user = await self.bot.api.get_user(user_login=user_str)
        channel = user
        # try:
        #     channel_obj = await self.bot.api.get_user(user_login=channel)
        # except NotFound:
        #     raise NotFound("Channel not found!")
        client = await self.bot.get_irc_client(ctx.guild, user)
        try:
            await client.send(channel, command)
        except NotConnected:
            try:
                async with aiofiles.open("connections.json") as f:
                    connections = json.loads(await f.read())
            except FileNotFoundError:
                connections = {}
            except json.decoder.JSONDecodeError:
                connections = {}
            await client.join(channel)
            connections[str(ctx.guild.id)][str(client.user.id)]["joined_channels"].append(channel.id)
            async with aiofiles.open("connections.json", "w") as f:
                await f.write(json.dumps(connections, indent=4))
            await client.send(channel, command)
            await ctx.send(f"Joined and sent message to #{channel.name}")
        else:
            await ctx.send(f"Sent message `{command}` to #{channel.name}")
        self.bot.log.info(f"Sent message in {channel.username} from {client.user.username} from guild {ctx.guild}")

    @commands.slash_command()
    @has_permissions()
    async def group(self, ctx: ApplicationCustomContext):
        pass

    @group.sub_command(name="new", description="Create a new group")
    async def group_new(self, ctx: ApplicationCustomContext, group_name: str):
        try:
            async with aiofiles.open("groups.json") as f:
                groups = json.loads(await f.read())
        except FileNotFoundError:
            groups = {}
        except json.decoder.JSONDecodeError:
            groups = {}
        if groups.get(str(ctx.guild.id), None) == None:
            groups[str(ctx.guild.id)] = {}
        if groups[str(ctx.guild.id)].get(group_name, None) != None:
            raise commands.BadArgument("Group name already exists!")
        groups[str(ctx.guild.id)][group_name] = []
        async with aiofiles.open("groups.json", "w") as f:
            await f.write(json.dumps(groups, indent=4))
        await ctx.send(f"Created group \"{group_name}\"")

    @group.sub_command(name="delete", description="Delete an existing group")
    async def group_delete(self, ctx: ApplicationCustomContext, group_name: str = commands.Param(autocomplete=group_autocomplete)):
        try:
            async with aiofiles.open("groups.json") as f:
                groups = json.loads(await f.read())
        except FileNotFoundError:
            groups = {}
        except json.decoder.JSONDecodeError:
            groups = {}
        if groups[str(ctx.guild.id)].get(group_name, None) == None:
            raise commands.BadArgument(f"Group \"{group_name}\" does not exist!")
        del groups[str(ctx.guild.id)][group_name]   
        if groups[str(ctx.guild.id)] == {}:
            del groups[str(ctx.guild.id)]
        async with aiofiles.open("groups.json", "w") as f:
            await f.write(json.dumps(groups, indent=4))
        await ctx.send(f"Deleted group \"{group_name}\"")

    @group.sub_command(name="add", description="Add client to group")
    async def group_add(self, ctx: ApplicationCustomContext, group_name: str = commands.Param(autocomplete=group_autocomplete), user: str = commands.Param(autocomplete=channel_autocomplete)):
        try:
            async with aiofiles.open("groups.json") as f:
                groups = json.loads(await f.read())
        except FileNotFoundError:
            groups = {}
        except json.decoder.JSONDecodeError:
            groups = {}
        if groups.get(str(ctx.guild.id), None) == None:
            groups[str(ctx.guild.id)] = {}
        if groups[str(ctx.guild.id)].get(group_name, None) == None:
            raise commands.BadArgument(f"Group \"{group_name}\" does not exist!")
        user_obj = await self.bot.api.get_user(user_login=user)
        groups[str(ctx.guild.id)][group_name].append(user_obj.id)
        async with aiofiles.open("groups.json", "w") as f:
            await f.write(json.dumps(groups, indent=4))
        await ctx.send(f"Added \"{user_obj.username}\" to group \"{group_name}\"")

    @group.sub_command(name="remove", description="Remove client from group")
    async def group_remove(self, ctx: ApplicationCustomContext, group_name: str = commands.Param(autocomplete=group_autocomplete), user: str = commands.Param(autocomplete=channel_group_autocomplete)):
        try:
            async with aiofiles.open("groups.json") as f:
                groups = json.loads(await f.read())
        except FileNotFoundError:
            groups = {}
        except json.decoder.JSONDecodeError:
            groups = {}
        if groups.get(str(ctx.guild.id), None) == None:
            groups[str(ctx.guild.id)] = {}
        if groups[str(ctx.guild.id)].get(group_name, None) == None:
            raise commands.BadArgument(f"Group \"{group_name}\" does not exist!")
        user_obj = await self.bot.api.get_user(user_login=user)
        if user_obj.id in groups[str(ctx.guild.id)][group_name]:
            groups[str(ctx.guild.id)][group_name].remove(user_obj.id)
        else:
            raise commands.BadArgument(f"Client \"{user_obj.username}\" not in group \"{group_name}\"!")
        async with aiofiles.open("groups.json", "w") as f:
            await f.write(json.dumps(groups, indent=4))
        await ctx.send(f"Removed \"{user_obj.username}\" from group \"{group_name}\"")

    @group.sub_command(name="list", description="List clients that are part of provided group")
    async def group_list(self, ctx: ApplicationCustomContext, group_name: str = commands.Param(autocomplete=group_autocomplete)):
        try:
            async with aiofiles.open("groups.json") as f:
                groups = json.loads(await f.read())
        except FileNotFoundError:
            groups = {}
        except json.decoder.JSONDecodeError:
            groups = {}
        if groups[str(ctx.guild.id)].get(group_name, None) == None:
            raise commands.BadArgument(f"Group \"{group_name}\" does not exist!")
        channels = [c.username for c in await self.bot.api.get_users(user_ids=groups[str(ctx.guild.id)][group_name])]
        await ctx.send(f"Group \"{group_name}\" has {len(groups[str(ctx.guild.id)][group_name])} client{'s' if len(groups[str(ctx.guild.id)][group_name]) != 1 else ''}\n**Clients:** {', '.join(channels)}")

    @commands.slash_command()
    @has_permissions()
    async def tokenexpiry(self, ctx: ApplicationCustomContext):
        pass

    @tokenexpiry.sub_command(name="setchannel", description="Set a text channel that will alert of expired tokens")
    async def tokenexpiry_setchannel(self, ctx: ApplicationCustomContext, channel: TextChannel):
        try:
            async with aiofiles.open("connections.json") as f:
                connections = json.loads(await f.read())
        except FileNotFoundError:
            connections = {}
        except json.decoder.JSONDecodeError:
            connections = {}
        if connections.get(str(ctx.guild.id), None) is None:
            connections[str(ctx.guild.id)] = {}
        # This line is just to ensure the expiry channel key is always at the top
        connections[str(ctx.guild.id)] = {"expiry_channel": channel.id, **connections[str(ctx.guild.id)]}
        async with aiofiles.open("connections.json", "w") as f:
            await f.write(json.dumps(connections, indent=4))
        await ctx.send(f"Set token expiry alert channel to {channel.mention}")

    @tokenexpiry.sub_command(name="remove", description="Remove the set channel for token expiry alerts")
    async def tokenexpiry_remove(self, ctx: ApplicationCustomContext):
        try:
            async with aiofiles.open("connections.json") as f:
                connections = json.loads(await f.read())
        except FileNotFoundError:
            connections = {}
        except json.decoder.JSONDecodeError:
            connections = {}
        if not connections.get(str(ctx.guild.id), {}).get("expiry_channel", None):
            return await ctx.send("Token expiry channel has not been set!")
        del connections[str(ctx.guild.id)]["expiry_channel"]
        if connections[str(ctx.guild.id)] == {}:
            del connections[str(ctx.guild.id)]
        async with aiofiles.open("connections.json", "w") as f:
            await f.write(json.dumps(connections, indent=4))
        await ctx.send(f"Removed the set token expiry channel")

    @commands.slash_command()
    @has_permissions()
    async def permissions(self, ctx: ApplicationCustomContext):
        pass

    @permissions.sub_command(name="grant", description="Grant the provided user access to the bot in this server")
    async def permissions_grant(self, ctx: ApplicationCustomContext, user: Member):
        try:
            async with aiofiles.open("permissions.json") as f:
                permissions = json.loads(await f.read())
        except FileNotFoundError:
            permissions = {}
        except json.decoder.JSONDecodeError:
            permissions = {}
        try:
            async with aiofiles.open("config.json") as f:
                auth = json.loads(await f.read())
        except FileNotFoundError:
            auth = {}
        except json.decoder.JSONDecodeError:
            auth = {}
        if user.id in auth.get("bot_owners", []) or user.id in permissions.get(str(ctx.guild.id), []):
            return await ctx.send("User already has access to the bot")
        if str(ctx.guild.id) not in permissions.keys():
            permissions[str(ctx.guild.id)] = []
        permissions[str(ctx.guild.id)].append(user.id)
        async with aiofiles.open("permissions.json", "w") as f:
            await f.write(json.dumps(permissions, indent=4))
        await ctx.send(f"Granted {user} access to the bot")

    @permissions.sub_command(name="revoke", description="Revoke the provided users access to the bot in this server")
    async def permissions_revoke(self, ctx: ApplicationCustomContext, user: Member):
        try:
            async with aiofiles.open("permissions.json") as f:
                permissions = json.loads(await f.read())
        except FileNotFoundError:
            permissions = {}
        except json.decoder.JSONDecodeError:
            permissions = {}
        try:
            async with aiofiles.open("config.json") as f:
                auth = json.loads(await f.read())
        except FileNotFoundError:
            auth = {}
        except json.decoder.JSONDecodeError:
            auth = {}
        if user.id in auth.get("bot_owners", []):
            return await ctx.send("Cannot revoke this users access to the bot")
        if user.id not in permissions.get(str(ctx.guild.id), []):
            return await ctx.send("User has not been granted access to the bot")
        permissions[str(ctx.guild.id)].remove(user.id)
        if permissions[str(ctx.guild.id)] == []:
            del permissions[str(ctx.guild.id)]
        async with aiofiles.open("permissions.json", "w") as f:
            await f.write(json.dumps(permissions, indent=4))
        await ctx.send(f"Revoked {user}'s access to the bot")

    @permissions.sub_command(name="list", description="List all users with permissions to use the bot in this server")
    async def permissions_list(self, ctx: ApplicationCustomContext):
        await ctx.response.defer()
        try:
            async with aiofiles.open("permissions.json") as f:
                permissions = json.loads(await f.read())
        except FileNotFoundError:
            permissions = {}
        except json.decoder.JSONDecodeError:
            permissions = {}
        try:
            async with aiofiles.open("config.json") as f:
                auth = json.loads(await f.read())
        except FileNotFoundError:
            auth = {}
        except json.decoder.JSONDecodeError:
            auth = {}
        users = [str(await self.bot.fetch_user(id)) for id in permissions.get(str(ctx.guild.id), [])]
        users += [str(await self.bot.fetch_user(id)) for id in auth.get("bot_owners", []) if id not in permissions.get(str(ctx.guild.id), [])]
        await ctx.send(f"{len(users)} user{'s' if len(users) != 1 else ''} {'have' if len(users) != 1 else 'has'} permissions to use the bot\n**Users:** {', '.join(users)}")

def setup(bot):
    bot.add_cog(IRCCommands(bot))