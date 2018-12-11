from util import *
import aiohttp

class Subst():
  """subst [...]
  see `subst help` for more info."""

  URL = 'https://admin.karinthy.hu/api/substitutions?day={date}'

  def getMotd(date: datetime.date, diffOnly: bool = False) -> str:
    """Get subst motd"""
    if diffOnly:
      motd = 'Here are {}\'s new substitutions:'
    else:
      motd = 'Here are {}\'s substitutions:'
    if datetime.date.today() == date:
      return motd.format('today')
    else:
      return motd.format('tomorrow')

  def format(raw: list, channelID: int, diffOnly: bool = False) -> discord.Embed:
    """Formats raw subst data"""
    strID = str(channelID)
    global state
    if not strID in state[CLASSOF]:
      embed = discord.Embed(title='Error!', type='rich', color=discord.Color.red(), description='ClassID not given!')
      return  embed
    classID = state[CLASSOF][strID]
    substEmbed = discord.Embed(type='rich', color=discord.Color.blue())
    empty = True
    for s in raw:
      if s['class'] == classID and (not diffOnly or s not in state[KNOWN_SUBSTS]):
        empty = False
        substEmbed.add_field(name=s['subject'] or '?', value='lesson {}\n{}\n{}\n~~{}~~\nroom {}'.format(
          s['lesson'] or '?', s['comment'] or '?', s['substitutingTeacher'] or '?', s['missingTeacher'] or '?', s['room'] or '?'))
    if empty:
      return None
    substEmbed.title = Subst.getMotd(datetime.date.fromisoformat(raw[0]['day']), diffOnly)
    return substEmbed

  async def acquire(date: datetime.date) -> list:
    """Downloads the substs on [date]"""
    URL = Subst.URL.format(date=date.isoformat())
    headers = {'Accept': 'application/json'}
    async with aiohttp.request('GET', URL, headers=headers) as response:
      return (await response.json())['substitutions']

  async def print(channel: discord.TextChannel, date: datetime.date) -> None:
    """Prints the substitutions on [date] to [channel]."""
    await channel.trigger_typing()
    substEmbed = Subst.format(await Subst.acquire(date), channel.id)
    if substEmbed == None:
      substEmbed = discord.Embed(title='There are no substitutions.', type='rich', color=discord.Color.blue())
    await channel.send(embed=substEmbed)


  #Commands:
  async def help(channel: discord.TextChannel, args: tuple) -> None:
    """help
    Print help."""
    helpEmbed = discord.Embed(title='Available subcommands for subst:', type='rich', color=discord.Color.blue())
    for command in Subst.commands.values():
      doc = command.__doc__.splitlines()
      helpEmbed.add_field(name=doc[0], value='\n'.join(doc[1:]))
    await channel.send(embed=helpEmbed)

  async def info(channel: discord.TextChannel, args: tuple) -> None: #TODO needs cleaning up
    """info
    Get info about this channel."""
    global state
    times = []
    for i in range(len(state[AUTO_SEND])):
      if str(channel.id) in state[AUTO_SEND][i][CHANNELS] and state[AUTO_SEND][i][CHANNELS][str(channel.id)][SUBST]:
        times.append(Util.timeAt(i).strftime('%H:%M'))
    if len(times) == 0:
      if str(channel.id) in state[AUTO_SUBST]:
        description = 'You will get substitution messages right when they get on the board.'
      else:
        description = 'Substitution messages are turned off for this channel.'
    else:
      if len(times) == 1:
        if str(channel.id) in state[AUTO_SUBST]:
          description = 'You will get substitution notifications at ' + times[0] + ' and right when they get on the board.'
        else:
          description = 'You will get lunch notifications at ' + times[0]
      else:
        if str(channel.id) in state[AUTO_SUBST]:
          description = 'You will get lunch notifications at the following times:\n' + '\n'.join(times) + '\nRight when they get on the board'
        else:
          description = 'You will get lunch notifications at the following times:\n' + '\n'.join(times)
    if str(channel.id) in state[CLASSOF]:
      description += "\nClass ID for this channel is {}".format(state[CLASSOF][str(channel.id)]) 
    else:
      description += "\nClass ID not set for this channel." 
    embed = discord.Embed(title='Subst info:', description=description,
        type='rich', color=discord.Color.blue())
    await channel.send(embed=embed)

  async def classID(channel: discord.TextChannel, args: tuple) -> None:
    """classID
    Set classID for this channel. Setting classID is required for all substitution operations."""
    global state
    if len(args) < 1:
      await Util.sendError(channel, 'ClassID isn\'t given.')
      return
    state[CLASSOF][str(channel.id)] = args[0]
    Util.saveState()
    await Util.sendSuccess(channel, 'The class ID for this channel is now {}'.format(args[0]))

  async def today(channel: discord.TextChannel, args: tuple) -> None:
    """today
    Print today's substitutions."""
    await Subst.print(channel, datetime.date.today())

  async def next(channel: discord.TextChannel, args: tuple) -> None:
    """next
    Print the substitutions on the next day which has lunch. Only checks the next week.""" #TODO no it doesn't
    await Subst.print(channel, datetime.date.today() + datetime.timedelta(days=1))

  async def on(channel: discord.TextChannel, args: tuple) -> None:
    """on [HH[:MM]]
    Turn on scheduled lunch messages at a given time. Multiple times can be set for a channel.
    If no time was given, turn on autoSubst which checks twice an hour if there are new substitutions."""
    global state
    if len(args) == 0:
      if str(channel.id) in state[AUTO_SUBST]:
        await Util.sendError(channel, 'Automatic substitution msessages are already enabled for this channel.')
        return
      state[AUTO_SUBST].append(str(channel.id))
      Util.saveState()
      Util.startAutoSend()
      await Util.sendSuccess(channel, 'You have enabled automatic substitution messages for this channel.')
    else:
      time = Util.parseTime(args[0])
      if time == None:
        await Util.sendError(channel, '{} isn\'t a valid time.'.format(' '.join(args)))
        return
      if Util.setStuff(time, channel, SUBST, True):
        await Util.sendSuccess(channel, 'You have enabled scheduled substitution messages for this channel! You will get them every day at {}.'.format(time.strftime('%H:%M')))
      else:
        await Util.sendError(channel, 'Scheduled substitution messages are already enabled for this channel at {}.'.format(time.strftime('%H:%M')))

  async def off(channel: discord.TextChannel, args: tuple) -> None:
    """off HH[:MM]
    Turn off scheduled substitution messages at a given time. You can get the current schedule for a channel with the info command.
    If no time was given, turn off autoSubst."""
    if len(args) == 0:
      if not str(channel.id) in state[AUTO_SUBST]:
        await Util.sendError(channel, 'Automatic substitution messages are already disabled for this channel.')
        return
      state[AUTO_SUBST].remove(str(channel.id))
      Util.saveState()
      Util.startAutoSend()
      await Util.sendSuccess(channel, 'You have disabled automatic substitution messages for this channel.')
    else:
      time = Util.parseTime(args[0])
      if time == None:
        await Util.sendError(channel, '{} isn\'t a valid time.'.format(' '.join(args)))
        return
      if Util.setStuff(time, channel, SUBST, False):
        await Util.sendSuccess(channel, 'You have disabled scheduled substitution messages for this channel at {}.'.format(time.strftime('%H:%M')))
      else:
        await Util.sendError(channel, 'There were no substitution messages scheduled for this channel at {}.'.format(time.strftime('%H:%M')))

  commands = {
    'help': help,
    'info': info,
    'classID': classID,
    'today': today,
    'next': next,
    'on': on,
    'off': off,
    }

