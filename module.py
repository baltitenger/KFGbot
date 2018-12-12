import discord;
import datetime;

class Module(object):
  """module [...]
  Short description of what the module does"""

  @classmethod
  def getCommands(self) -> dict:
    return {
      "module": Module,
    };

  @classmethod
  def getSubcommands(self) -> dict:
    return {
      "help": self.help,
    };

  @classmethod
  def getSchedule(self) -> list:
    return [];

  @classmethod
  def save(self) -> dict:
    return {};

  @classmethod
  def load(self, data: dict):
    pass;

  @classmethod
  async def handleSchedule(self, index: datetime.time):
    pass;

  @classmethod
  async def doCheck(self):
    pass;

  @classmethod
  async def handleReaction(self, reaction: discord.Reaction, user: discord.User, add: bool) -> bool:
    return False;

  @classmethod
  def getDocEmbed(self) -> discord.Embed:
    docEmbed = discord.Embed(title="Available subcommands:", color=discord.Color.blue());
    for command in self.getSubcommands().values():
      doc = command.__doc__.splitlines();
      docEmbed.add_field(name="`{}`".format(doc[0]), value='\n'.join(doc[1:]));
    return docEmbed;

  #commands:
  async def help(channel: discord.TextChannel, args: tuple):
    """help
    Print help for the module."""
    await channel.send(embed=getDocEmbed());
