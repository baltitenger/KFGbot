import discord;

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
  def getSchedule(self) -> dict:
    return {};

  @classmethod
  def getChecks(self) -> list:
    return [];

  @classmethod
  def handleReaction(self, reaction: discord.Reaction, user: discord.User, add: bool) -> bool:
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
