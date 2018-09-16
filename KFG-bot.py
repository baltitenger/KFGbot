#!/usr/bin/python3 -u

import discord
import asyncio
import datetime
import urllib.request
import xml.etree.ElementTree as ET
import json

from subprocess import run
# import io


client = discord.client.Client()
autoSendTask = None


# constants
LUNCH_URL = 'https://naplo.karinthy.hu/app/interface.php?view=v_canteen_export&day={date}' 
SUBST_URL = 'https://admin.karinthy.hu/api/substitutions?day={date}'
PLOT_OPTS = 'set term png crop size 1000, 1000; set size ratio -1; set samples 1000; set xrange [-10:10]; set yrange [-10:10]; set grid; set zeroaxis; set key off; plot {function}'
STATE_FILE = 'state.json'
AUTO_SEND = 'autoSend'
AUTO_SUBST = 'autoSubst'
CLASSOF = 'classOf'
COUNTDOWN = 'countdown'
ISOTIME = 'isotime'
CHANNELS = 'channels'
NO_MENTION = 'noMention'
LUNCH = 'lunch'
SUBST = 'subst'
KNOWN_SUBSTS = 'knownSubsts'
state = {AUTO_SEND:[], AUTO_SUBST:[], CLASSOF:{}, COUNTDOWN:{}, NO_MENTION:[], KNOWN_SUBSTS:[]}
## state: {AUTO_SEND:[{ISOTIME:isotime, CHANNELS:{channelId:{LUNCH:bool, SUBST:bool}, ...}}, ...], AUTO_SUBST:[channelID, ...], CLASSOF:{channelId:class, ...}, COUNTDOWN:{channelId:msgId, ...}, KNOWN_SUBSTS:[]}
#TODO nyelvorak?

class Util():
  def timeAt(index) -> datetime.time:
    if len(state[AUTO_SEND]) == 0:
      return None
    else:
      return datetime.time.fromisoformat(state[AUTO_SEND][index % len(state[AUTO_SEND])][ISOTIME])


  def indexOf(time) -> int: 
    if len(state[AUTO_SEND]) == 0:
      return 0
    bot = 0
    top = len(state[AUTO_SEND]) - 1
    if time < Util.timeAt(bot):
      return bot
    if Util.timeAt(top) < time:
      return top + 1
    while True:
      avg = (top + bot) // 2
      if Util.timeAt(avg) == time:
        return avg
      elif Util.timeAt(avg) < time:
        bot = avg
      else:
        top = avg
      if top - bot == 1:
        return top


  def parseTime(stringTime) -> datetime.time:
    try:
      splitTime = stringTime.split(':')
      hour = int(splitTime[0])
      if len(splitTime) == 2:
        minute = int(splitTime[1])
      else:
        minute = 0
      return datetime.time(hour, minute)
    except ValueError:
      return None


  def parseDate(stringDate) -> datetime.date:
    try:
      splitDate = stringDate.split('-')
      day = int(splitDate[len(splitDate) - 1])
      if len(splitDate) >= 2:
        month = int(splitDate[len(splitDate) - 2])
      else:
        month = datetime.date.today().month
      if len(splitDate) == 3:
        year = int(splitDate[0])
      else:
        year = datetime.date.today().year
      return datetime.date(year, month, day)
    except ValueError:
      return None


  def startAutoSend():
    global autoSendTask
    if autoSendTask != None:
      autoSendTask.cancel()
      autoSendTask = None
    if len(state[AUTO_SEND]) > 0 or len(state[AUTO_SUBST]) > 0:
      autoSendTask = client.loop.create_task(autoSend())


  def setStuff(time, channel, thingToSet, to): # TODO find a better name for this too
    index = Util.indexOf(time)
    strID = str(channel.id)
    if index < len(state[AUTO_SEND]) and state[AUTO_SEND][index][ISOTIME] == time.isoformat():
      if strID in state[AUTO_SEND][index][CHANNELS]:
        if state[AUTO_SEND][index][CHANNELS][strID][thingToSet] == to:
          return False
        else:
          state[AUTO_SEND][index][CHANNELS][strID][thingToSet] = to
      else:
        state[AUTO_SEND][index][CHANNELS].append({strID:{LUNCH:False, SUBST:False}})
    else:
      state[AUTO_SEND].insert(index, {ISOTIME:time.isoformat(), CHANNELS:{strID:{LUNCH:False, SUBST:False}}})
    state[AUTO_SEND][index][CHANNELS][strID][thingToSet] = to
    if not (state[AUTO_SEND][index][CHANNELS][strID][LUNCH] or state[AUTO_SEND][index][CHANNELS][strID][SUBST]):
      state[AUTO_SEND][index][CHANNELS].pop(strID)
      if len(state[AUTO_SEND][index][CHANNELS]) == 0:
        state[AUTO_SEND].pop(index)
    Util.saveState()
    Util.startAutoSend()
    return True


  async def sendSuccess(channel, message):
    embed = discord.Embed(title='Success!', type='rich', color=discord.Color.green(), description=message)
    await channel.send(embed=embed)


  async def sendError(channel, message):
    embed = discord.Embed(title='Error!', type='rich', color=discord.Color.red(), description=message)
    await channel.send(embed=embed)


  def saveState(): # export current state to state.json
    with open(STATE_FILE, 'w') as stateFile: # open file for writing
      json.dump(state, stateFile)


  def loadState(): # import schedules saved in jsons
    global state
    try:
      with open(STATE_FILE, 'r') as stateFile: # open file for reading
        state = json.load(stateFile)
    except FileNotFoundError:
      pass
    except json.decoder.JSONDecodeError as e:
      print('Invalid state.json!')
      print(e.msg)


async def autoSend():
  i = Util.indexOf(datetime.datetime.now().time())
  print('autoSend started...')
  while True:
    now = datetime.datetime.now()
    nextTime = datetime.datetime.combine(now.date(), Util.timeAt(i))
    if i == len(state[AUTO_SEND]): # -> next time to send is tomorrow
      i = 0
      nextTime += datetime.timedelta(days=1)
    while nextTime - now > datetime.timedelta(seconds=30 * 60):
      date = now.date()
      if now.time() > datetime.time(15, 00):
        date += datetime.timedelta(days=1)
      substs = Subst.downloadSubsts(date)
      for channelID in state[AUTO_SUBST]:
        substEmbed = Subst.format(substs, channelID, True)
        if substEmbed != None:
          await client.get_channel(int(channelID)).send(embed=substEmbed)
      state[KNOWN_SUBSTS] = substs
      print('Waiting 30 minutes...')
      await asyncio.sleep(30 * 60)
      now = datetime.datetime.now()
    print((nextTime - now).seconds, 'seconds to the next print.')
    await asyncio.sleep((nextTime - now).seconds)
    print('Printing...')
    now = datetime.datetime.now()
    date = now.date()
    if now.time() > datetime.time(15, 00):
      date += datetime.timedelta(days=1)
    lunchEmbed = Lunch.generateEmbed(date)
    substs = Subst.downloadSubsts(date)
    for channelID, send in state[AUTO_SEND][i][CHANNELS].items():
      if send[LUNCH] and lunchEmbed != None:
        await client.get_channel(int(channelID)).send(embed=lunchEmbed)
      if send[SUBST] and substs != None:
        substEmbed = Subst.format(substs, channelID)
        if substEmbed != None:
          await client.get_channel(int(channelID)).send(embed=substEmbed)
    i += 1


#Commands:
async def help(channel, args):
  """help
  Print help."""
  helpEmbed = discord.Embed(title='Available commands:', type='rich', color=discord.Color.blue())
  for command in commands.values():
    doc = command.__doc__.splitlines()
    helpEmbed.add_field(name=doc[0], value='\n'.join(doc[1:]))
  await channel.send(embed=helpEmbed)


async def ping(channel, args): # ping [delay]
  """ping [delay]
  Reply with `pong` after [delay] seconds."""
  if len(args) == 1:
    try:
      await asyncio.sleep(int(args[0]))
    except ValueError:
      pass
  await channel.send("pong") 


async def plot(channel, args): # can throw exception, unhandled for now
  """plot function
  Reply with an image of the plot of [function]. See the documentation of gnuplot for additional info."""
  await channel.trigger_typing()
  function = ''.join(args)
  output = run(['gnuplot', '-e', PLOT_OPTS.format(function=function)], capture_output=True)
  if output.returncode == 0:
    await channel.send("Plot of `{}`:".format(function), file=discord.File(output.stdout, filename="plot.png"))
  else:
    await Util.sendError(channel, output.stderr.decode('utf-8'))


async def mention(channel, args):
  """mention
  toggles optional/recquired mentioning the bot."""
  if str(channel.id) in state[NO_MENTION]:
    state[NO_MENTION].remove(str(channel.id))
    await Util.sendSuccess(channel, 'Mentioning the bot is now required.')
  else:
    state[NO_MENTION].append(str(channel.id))
    await Util.sendSuccess(channel, 'Mentioning the bot is now optional.')
  Util.saveState()


class Lunch():
  """lunch [...]
  see `lunch help` for more info."""
  def getMotd(date) -> str:
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


  def format(rawlunch, date) -> discord.Embed:
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
      return (discord.Embed(title=Lunch.getMotd(date), type='rich', color=discord.Color.blue())
          .add_field(name='Leves:', value=soup)
          .add_field(name='A menü:', value=a)
          .add_field(name='B menü:', value=b)
          .add_field(name='C menü:', value=c)
          .set_footer(text='Have fun!'))
    except:
      return discord.Embed(title=Lunch.getMotd(date), type='rich', color=discord.Color.blue(), description=rawlunch) # if lunch formatting failed, just print it out unformatted


  def acquire(date) -> str:
    """Downloads the lunch on [date]"""
    URL = LUNCH_URL.format(date=date.isoformat())
    with urllib.request.urlopen(URL) as response:
      lunch_xml = response.read().decode('utf-8') # get lunchxml
      root = ET.fromstring(lunch_xml) # parse it
      return root[2].text # get the relevant part


  async def print(channel, date) -> None:
    """Prints the lunch on [date] to [channel]."""
    await channel.trigger_typing()
    lunchEmbed = Lunch.format(Lunch.acquire(date), date)
    if lunchEmbed == None:
      await Util.sendError(channel, 'The lunch for ' + date.isoformat() + ' isn\'t available yet/anymore, or there\'s no lunch on the date specified.')
    else:
      await channel.send(embed=lunchEmbed)

  
  #Commands:
  async def help(channel, args) -> None:
    """help
    Print help."""
    helpEmbed = discord.Embed(title='Available subcommands for lunch:', type='rich', color=discord.Color.blue())
    for command in Lunch.commands.values():
      doc = command.__doc__.splitlines()
      helpEmbed.add_field(name=doc[0], value='\n'.join(doc[1:]))
    await channel.send(embed=helpEmbed)


  async def info(channel, args) -> None:
    """info
    Get info about this channel."""
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


  async def today(channel, args) -> None:
    """today
    Print today's lunch."""
    await Lunch.print(channel, datetime.date.today())


  async def next(channel, args) -> None:
    """next
    Print the lunch on the next day which has lunch. Only checks the next week.""" #TODO no it doesn't
    await Lunch.print(channel, datetime.date.today() + datetime.timedelta(days=1))


  async def day(channel, args) -> None:
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


  async def on(channel, args) -> None:
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


  async def off(channel, args) -> None:
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


class Subst():
  """subst [...]
  see `subst help` for more info."""
  def getMotd(date, diffOnly):
    """Get subst motd"""
    if diffOnly:
      motd = 'Here are {}\'s new substitutions:'
    else:
      motd = 'Here are {}\'s substitutions:'
    if datetime.date.today() == date:
      return motd.format('today')
    else:
      return motd.format('tomorrow')


  def format(raw, channelID, diffOnly=False):
    """Formats raw subst data"""
    if not channelID in state[CLASSOF]:
      embed = discord.Embed(title='Error!', type='rich', color=discord.Color.red(), description='ClassID not given!')
      return  embed
    classID = state[CLASSOF][channelID]
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


  def acquire(date):
    """Downloads the substs on [date]"""
    request = urllib.request.Request(SUBST_URL.format(date=date.isoformat()))
    request.add_header('Accept', 'application/json')
    with urllib.request.urlopen(request) as response:
      return json.load(response)['substitutions']


  async def print(channel, date):
    """Prints the substitutions on [date] to [channel]."""
    await channel.trigger_typing()
    substEmbed = Subst.format(Subst.acquire(date), str(channel.id))
    if substEmbed == None:
      substEmbed = discord.Embed(title='There are no substitutions.', type='rich', color=discord.Color.blue())
    await channel.send(embed=substEmbed)


  #Commands:
  async def help(channel, args):
    """help
    Print help."""
    helpEmbed = discord.Embed(title='Available subcommands for subst:', type='rich', color=discord.Color.blue())
    for command in Subst.commands.values():
      doc = command.__doc__.splitlines()
      helpEmbed.add_field(name=doc[0], value='\n'.join(doc[1:]))
    await channel.send(embed=helpEmbed)


  async def info(channel, args): #TODO needs cleaning up
    """info
    Get info about this channel."""
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


  async def classID(channel, args):
    """classID
    Set classID for this channel. Setting classID is required for all substitution operations."""
    if len(args) < 1:
      await Util.sendError(channel, 'ClassID isn\'t given.')
      return
    state[CLASSOF][str(channel.id)] = args[0]
    Util.saveState()
    await Util.sendSuccess(channel, 'The class ID for this channel is now {}'.format(args[0]))


  async def today(channel, args):
    """today
    Print today's substitutions."""
    await Subst.print(channel, datetime.date.today())


  async def next(channel, args):
    """next
    Print the substitutions on the next day which has lunch. Only checks the next week.""" #TODO no it doesn't
    await Subst.print(channel, datetime.date.today() + datetime.timedelta(days=1))


  async def on(channel, args):
    """on [HH[:MM]]
    Turn on scheduled lunch messages at a given time. Multiple times can be set for a channel.
    If no time was given, turn on autoSubst which checks twice an hour if there are new substitutions."""
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


  async def off(channel, args):
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


class HomeWork():
  """hw [...]
  see `hw help` for more info."""
  pass


commands = {
  'help': help,
  'ping': ping,
  'plot': plot,
  'mention': mention,
  'lunch': Lunch,
  'subst': Subst,
  'hw': HomeWork,
  }


@client.event
async def on_ready():
  global autoSendTask
  Util.startAutoSend()
  print('Ready!')


@client.event
async def on_message(message):
  channel = message.channel
  if message.author == client.user or not (client.user in message.mentions or type(channel) == discord.channel.DMChannel or str(channel.id) in state[NO_MENTION]):
    return
  splitMessage = message.content.split(' ')
  if client.user in message.mentions:
    splitMessage.pop(0)
  command = commands.get(splitMessage[0])
  found = False
  args = splitMessage[1:]
  if isinstance(command, type):
    subCommands = getattr(command, 'commands')
    if args[0] in subCommands:
      await subCommands[args[0]](channel, args[1:])
      found = True
  else:
    await command(channel, args)
    found = True
  if not found and client.user in message.mentions:
    await Util.sendError(channel, 'Unknown command.')


print('Starting...')

Util.loadState()

try:
    with open('token') as f: token = f.readline().strip()
    client.loop.run_until_complete(client.start(token))
except FileNotFoundError:
    print('Token file not found.')
    raise
except KeyboardInterrupt: # stop without error on KeyboardInterrupt
    client.loop.run_until_complete(client.logout())
    # cancel all tasks lingering
finally:
    client.loop.close()
    print('Finished.')

