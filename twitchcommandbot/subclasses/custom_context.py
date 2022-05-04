from disnake import ApplicationCommandInteraction
from disnake.utils import snowflake_time

class ApplicationCustomContext(ApplicationCommandInteraction):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.bot.intents.members:
            if self.guild:
                self.author = self.guild.get_member(self.author.id)
            else:
                self.author = self.bot.get_user(self.author.id)
        self.edit = self.edit_original_message

    @property
    def created_at(self):
        return snowflake_time(self.id)