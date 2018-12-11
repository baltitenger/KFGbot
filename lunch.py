from util import *
import aiohttp
from xml.etree import ElementTree

class Lunch():
  """lunch [...]
  see `lunch help` for more info."""

  URL = 'https://naplo.karinthy.hu/app/interface.php?view=v_canteen_export&day={date}' 

  def getMotd(date: datetime.date) -> str:
    """Get lunch motd"""
    if date == datetime.date.today():
      if datetime.datetime.now().time() > datetime.time(15, 00):
        return 'Today\'s lunch was:'
      else:
        return 'Here\'s today\'s lunch:'
    elif date == datetime.date.today() + datetime.timedelta(days = 1):
      return 'Tomorrow\'s lunch will be:'
    elif date < datetime.date.today():
      return 'The lunch on ' + date.isoformat() + ' was:'
    else:
      return 'The lunch on ' + date.isoformat() + ' will be:'

  def format(rawlunch: str, date: datetime.date) -> discord.Embed:
    """Formats raw lunch"""
    try:
      lunch = rawlunch.split('\n\n')
      a = lunch[0].split('\n')[1:]
      b = lunch[1].split('\n')[1:]
      c = lunch[2].split('\n')[1:]
      soup = []
      while a[0] == b[0]: # separate soup from the rest
        soup.append(a.pop(0))
        b.pop(0)
        c.pop(0)
      a = '\n'.join(a)
      b = '\n'.join(b)
      c = '\n'.join(c)
      soup = '\n'.join(soup)
      if soup == '':
        raise ValueError
      return (discord.Embed(title=Lunch.getMotd(date), type='rich', color=discord.Color.blue())
          .add_field(name='Leves:', value=soup)
          .add_field(name='A menü:', value=a)
          .add_field(name='B menü:', value=b)
          .add_field(name='C menü:', value=c)
          .set_footer(text='Have fun!'))
    except:
      return discord.Embed(title=Lunch.getMotd(date), type='rich', color=discord.Color.blue(), description=rawlunch) # if lunch formatting failed, just print it out unformatted

  async def acquire(date: datetime.date) -> str:
    """Downloads the lunch on [date]"""
    URL = Lunch.URL.format(date=date.isoformat())
    async with aiohttp.request('GET', URL) as response:
      lunch_xml = await response.text('utf-8') # get lunch xml
      root = ElementTree.fromstring(lunch_xml) # parse it
      return root[2].text # get the relevant part

  async def print(channel: discord.TextChannel, date: datetime.date) -> None:
    """Prints the lunch on [date] to [channel]."""
    await channel.trigger_typing()
    lunchEmbed = Lunch.format(await Lunch.acquire(date), date)
    if lunchEmbed == None:
      await Util.sendError(channel, 'The lunch for ' + date.isoformat() + ' isn\'t available yet/anymore, or there\'s no lunch on the date specified.')
    else:
      await channel.send(embed=lunchEmbed)
  

  #Commands:
  async def help(channel: discord.TextChannel, args: tuple) -> None:
    """help
    Print help."""
    helpEmbed = discord.Embed(title='Available subcommands for lunch:', type='rich', color=discord.Color.blue())
    for command in Lunch.commands.values():
      doc = command.__doc__.splitlines()
      helpEmbed.add_field(name=doc[0], value='\n'.join(doc[1:]))
    await channel.send(embed=helpEmbed)

  async def info(channel: discord.TextChannel, args: tuple) -> None:
    """info
    Get info about this channel."""
    global state
    times = []
    for i in range(len(state[AUTO_SEND])):
      if str(channel.id) in state[AUTO_SEND][i][CHANNELS] and state[AUTO_SEND][i][CHANNELS][str(channel.id)][LUNCH]:
        times.append(Util.timeAt(i).strftime('%H:%M'))
    description = None
    if len(times) == 0:
      title = 'There aren\'t any lunch messages scheduled for this channel.'
    elif len(times) == 1:
      title = 'You will get lunch messages at {}.'.format(times[0])
    else:
      title = 'You will get lunch notifications at the following times:'
      description = '\n'.join(times)
    embed = discord.Embed(title=title, description=description, type='rich', color=discord.Color.blue())
    await channel.send(embed=embed)

  async def today(channel: discord.TextChannel, args: tuple) -> None:
    """today
    Print today's lunch."""
    await Lunch.print(channel, datetime.date.today())

  async def next(channel: discord.TextChannel, args: tuple) -> None:
    """next
    Print the lunch on the next day which has lunch. Only checks the next week.""" #TODO no it doesn't
    await Lunch.print(channel, datetime.date.today() + datetime.timedelta(days=1))

  async def day(channel: discord.TextChannel, args: tuple) -> None:
    """day [[YYYY-]MM-]DD
    Print the lunch on the specified date."""
    if len(args) != 1:
      await Util.sendError(channel, 'Date isn\'t given.')
      return
    date = Util.parseDate(args[0])
    if date == None:
      await Util.sendError(channel, '{} isn\'t a valid date.'.format(' '.join(args)))
      return
    await Lunch.print(channel, date)

  async def on(channel: discord.TextChannel, args: tuple) -> None:
    """on HH[:MM]
    Turn on scheduled lunch messages at a given time. Multiple times can be set for a channel."""
    if len(args) < 1:
      await Util.sendError(channel, 'Time isn\'t given.')
      return
    time = Util.parseTime(args[0])
    if time == None:
      await Util.sendError(channel, '{} isn\'t a valid time.'.format(' '.join(args)))
      return
    if Util.setStuff(time, channel, LUNCH, True):
      await Util.sendSuccess(channel, 'You have enabled scheduled lunch messages for this channel! You will get them every day at {}.'.format(time.strftime('%H:%M')))
    else:
      await Util.sendError(channel, 'Scheduled lunch messages are already enabled for this channel at {}.'.format(time.strftime('%H:%M')))

  async def off(channel: discord.TextChannel, args: tuple) -> None:
    """off HH[:MM]
    Turn off scheduled lunch messages at a given time. You can get the current schedule for a channel with the info command."""
    if len(args) < 1:
      await Util.sendError(channel, 'Time isn\'t given')
      return
    time = Util.parseTime(args[0])
    if time == None:
      await Util.sendError(channel, '{} isn\'t a valid time.'.format(' '.join(args)))
      return
    if Util.setStuff(time, channel, LUNCH, False):
      await Util.sendSuccess(channel, 'You have disabled scheduled lunch messages for this channel at {}.'.format(time.strftime('%H:%M')))
    else:
      await Util.sendError(channel, 'There were no lunch messages scheduled for this channel at {}.'.format(time.strftime('%H:%M')))

  commands = {
    'help': help,
    'info': info,
    'today': today,
    'next': next,
    'day': day,
    'on': on,
    'off': off,
    }

