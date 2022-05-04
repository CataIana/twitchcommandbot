import disnake
from disnake.ext import commands
from twitchcommandbot.subclasses import ApplicationCustomContext
from types import BuiltinFunctionType, FunctionType, MethodType, CoroutineType
from time import time
from collections import deque
from collections.abc import Mapping
from textwrap import shorten
import asyncio
from munch import munchify
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from main import TwitchCommandBot

class ETCCommands(commands.Cog):
    def __init__(self, bot):
        self.bot: TwitchCommandBot = bot
        super().__init__()

    @commands.Cog.listener()
    async def on_raw_interaction(self, interaction):
        await self.bot.wait_until_ready()
        if interaction["type"] != 2:
            return
        ctx = await self.bot.get_slash_context(interaction, cls=ApplicationCustomContext)
        await self.bot.application_invoke(ctx)

    @commands.Cog.listener()
    async def on_slash_command(self, ctx: ApplicationCustomContext):
        if ctx.application_command:
            self.bot.log.info(f"Handling slash command {ctx.application_command.qualified_name} for {ctx.author} in {ctx.guild.name}")
        else:
            self.bot.log.info(f"Attemped to run invalid slash command!")

    #@commands.slash_command(description="Responds with the bots latency to discords servers")
    async def ping(self, ctx: ApplicationCustomContext):
        gateway = int(self.bot.latency*1000)
        await ctx.send(f"Pong! `{gateway}ms` Gateway") #Message cannot be ephemeral for ping updates to show

    async def aeval(self, ctx: ApplicationCustomContext, code):
        code_split = ""
        code_length = len(code.split("\\n"))
        for count, line in enumerate(code.split("\\n"), 1):
            if count == code_length:
                code_split += f"    return {line}"
            else:
                code_split += f"    {line}\n"
        combined = f"async def __ex(self, ctx):\n{code_split}"
        exec(combined)
        return await locals()['__ex'](self, ctx)

    def remove_tokens(self, string: str) -> str:
        vars = [
            self.bot.token,
            str(self.bot.auth)
        ]
        for var in vars:
            string = string.replace(var, "<Hidden>")
        return string

    async def eval_autocomplete(ctx: disnake.ApplicationCommandInteraction, com: str):
        if not await ctx.bot.is_owner(ctx.author):
            return ["You do not have permission to use this command"]
        self = ctx.application_command.cog
        com = com.split("await ", 1)[-1] # Strip await
        try:
            com_split = '.'.join(com.split(".")[:-1])
            var_request = '.'.join(com.split(".")[-1:])
            if com_split == '':
                com_split = var_request
                var_request = None
            resp = await self.aeval(ctx, com_split)
            if isinstance(resp, CoroutineType):
                resp = await resp
        except Exception as ex:
            return ["May want to keep typing...", "Exception: ", str(ex), com]
        else:
            if type(resp) == str:
                return [resp]
            if type(resp) == dict:
                resp = munchify(resp)

            attributes = [] #List of all attributes
            #get a list of all attributes and their values, along with all the functions in seperate lists
            for attr_name in dir(resp):
                try:
                    attr = getattr(resp, attr_name)
                except AttributeError:
                    pass
                if attr_name.startswith("_"):
                    continue #Most methods/attributes starting with __ or _ are generally unwanted, skip them
                if type(attr) not in [MethodType, BuiltinFunctionType, FunctionType]:
                    if var_request:
                        if not str(attr_name).startswith(var_request):
                            continue
                    if isinstance(attr, (list, deque)):
                        attributes.append(shorten(com_split + "." + self.remove_tokens(
                                f"{str(attr_name)}: {type(attr).__name__.title()}[{type(attr[0]).__name__.title() if len(attr) != 0 else 'None'}] [{len(attr)}]"), width=100))
                    elif isinstance(attr, (dict, commands.core._CaseInsensitiveDict, Mapping)):
                        attributes.append(shorten(com_split + "." + self.remove_tokens(
                                f"{str(attr_name)}: {type(attr).__name__.title()}[{type(list(attr.keys())[0]).__name__ if len(attr) != 0 else 'None'}, {type(list(attr.values())[0]).__name__ if len(attr) != 0 else 'None'}] [{len(attr)}]"), width=100))
                    elif type(attr) == set:
                        attr_ = list(attr)
                        attributes.append(shorten(com_split + "." + self.remove_tokens(
                                f"{str(attr_name)}: {type(attr).__name__.title()}[{type(attr_[0]).__name__.title() if len(attr) != 0 else 'None'}] [{len(attr)}]"), width=100))
                    else:
                        b = com_split + "." + self.remove_tokens(str(attr_name)) + ": {} [" + type(attr).__name__ + "]"
                        attributes.append(b.format(str(attr)[:100-len(b)-5] + " [...]"))
                else:
                    if var_request:
                        if not str(attr_name).startswith(var_request):
                            continue
                    if asyncio.iscoroutinefunction(attr):
                        attributes.append(shorten(com_split + "." + f"{str(attr_name)}: [async {type(attr).__name__}]", width=100))
                    else:
                        attributes.append(shorten(com_split + "." + f"{str(attr_name)}: [{type(attr).__name__}]", width=100))
            return attributes[:25]
    
    #@commands.slash_command(description="Evalute a string as a command")
    #@commands.is_owner()
    async def eval(self, ctx: ApplicationCustomContext, command: str = commands.Param(autocomplete=eval_autocomplete), respond: bool = True):
        command = command.split(":")[0]
        show_all = False
        code_string = "```nim\n{}```"
        if command.startswith("`") and command.endswith("`"):
            command = command[1:][:-1]
        start = time()
        try:
            resp = await self.aeval(ctx, command)
            if isinstance(resp, CoroutineType):
                resp = await resp
        except Exception as ex:
            await ctx.send(content=f"Exception Occurred: `{type(ex).__name__}: {ex}`")
        else:
            finish = time()
            if respond:
                if type(resp) == str:
                    return await ctx.send(code_string.format(resp))

                attributes = {} #Dict of all attributes
                methods = [] #Sync methods
                amethods = [] #Async methods
                #get a list of all attributes and their values, along with all the functions in seperate lists
                for attr_name in dir(resp):
                    try:
                        attr = getattr(resp, attr_name)
                    except AttributeError:
                        pass
                    if not show_all:
                        if attr_name.startswith("_"):
                            continue #Most methods/attributes starting with __ or _ are generally unwanted, skip them
                    if type(attr) not in [MethodType, BuiltinFunctionType, FunctionType]:
                        if isinstance(attr, (list, deque)):
                            attributes[str(attr_name)] = f"{type(attr).__name__.title()}[{type(attr[0]).__name__.title() if len(attr) != 0 else 'None'}] [{len(attr)}]"
                        elif isinstance(attr, (dict, commands.core._CaseInsensitiveDict, Mapping)):
                            attributes[str(attr_name)] = f"{type(attr).__name__.title()}[{type(list(attr.keys())[0]).__name__ if len(attr) != 0 else 'None'}, {type(list(attr.values())[0]).__name__ if len(attr) != 0 else 'None'}] [{len(attr)}]"
                        elif type(attr) == set:
                            attr_ = list(attr)
                            attributes[str(attr_name)] = f"{type(attr).__name__.title()}[{type(attr_[0]).__name__.title() if len(attr) != 0 else 'None'}] [{len(attr)}]"
                        else:
                            attributes[str(attr_name)] = f"{attr} [{type(attr).__name__}]"
                    else:
                        if asyncio.iscoroutinefunction(attr):
                            amethods.append(attr_name)
                        else:
                            methods.append(attr_name)

                #Form the long ass string of everything
                return_string = []
                if type(resp) != list:
                    stred = str(resp)
                else:
                    stred = '\n'.join([str(r) for r in resp])
                return_string += [f"Type: {type(resp).__name__}", f"String: {stred}"] #List return type, it's str value
                if attributes != {}:
                    return_string += ["", "Attributes: "]
                    return_string += [self.remove_tokens(f"{x+': ':20s}{shorten(y, width=(106-len(x)))}") for x, y in attributes.items()]

                if methods != []:
                    return_string.append("\nMethods:")
                    return_string.append(', '.join([method for method in methods]).rstrip(", "))

                if amethods != []:
                    return_string.append("\nAsync/Awaitable Methods:")
                    return_string.append(', '.join([method for method in amethods]).rstrip(", "))

                return_string.append(f"\nTook {((finish-start)*1000):2f}ms to process eval")

                d_str = ""
                for x in return_string:
                    if len(d_str + f"{x.rstrip(', ')}\n") < 1990:
                        d_str += f"{x.rstrip(', ')}\n"
                    else:
                        if len(code_string.format(d_str)) > 2000:
                            while d_str != "":
                                await ctx.send(code_string.format(d_str[:1990]))
                                d_str = d_str[1990:]
                        else:
                            await ctx.send(code_string.format(d_str))
                        d_str = f"{x.rstrip(', ')}\n"
                if d_str != "":
                    try:
                        await ctx.send(code_string.format(d_str))
                    except disnake.errors.NotFound:
                        pass

    @commands.slash_command(description="Owner Only: Reload the bot cogs and listeners")
    @commands.is_owner()
    async def reload(self, ctx: ApplicationCustomContext):
        cog_count = 0
        for ext_name in dict(self.bot.extensions).keys():
            cog_count += 1
            self.bot.reload_extension(ext_name)
        await ctx.send(f"Succesfully reloaded! Reloaded {cog_count} cogs!", ephemeral=True)

def setup(bot):
    bot.add_cog(ETCCommands(bot))