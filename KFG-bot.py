#!/usr/bin/python3 -u

import discord
import asyncio
import datetime
import urllib.request
import xml.etree.ElementTree as ET
import json

import matplotlib.pyplot as plt
import numpy as np
import numexpr
import io


client = discord.client.Client()
autoSendTask = None


# constants
LUNCH_URL = 'https://naplo.karinthy.hu/app/interface.php?view=v_canteen_export&day={date}' 
SUBST_URL = 'https://admin.karinthy.hu/api/substitutions?day={date}'
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
state = {AUTO_SEND:[], AUTO_SUBST:[], CLASSOF:{}, COUNTDOWN:{}, NO_MENTION:[]}
## state: {AUTO_SEND:[{ISOTIME:isotime, CHANNELS:{channelId:{LUNCH:bool, SUBST:bool}, ...}}, ...], AUTO_SUBST:[channelID, ...], CLASSOF:{channelId:class, ...}, COUNTDOWN:{channelId:msgId, ...}}


class Util():
  def timeAt(index):
    if len(state[AUTO_SEND]) == 0:
      return None
    else:
      return datetime.time.fromisoformat(state[AUTO_SEND][index % len(state[AUTO_SEND])][ISOTIME])


  def indexOf(time): 
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


  def parseTime(stringTime):
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


  def parseDate(stringDate):
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
    global autoSendTask
    if autoSendTask != None:
      autoSendTask.cancel()
    if len(state[AUTO_SEND]) > 0:
      autoSendTask = client.loop.create_task(autoSend())
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


class Lunch():
  def getMotd(date): # get lunch motd depending on date queried
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


  def format(rawlunch, date):
    try:
      lunch = rawlunch.split('\n\n')
      a = lunch[0].split('\n')[1:]
      b = lunch[1].split('\n')[1:]
      soup = []
      while a[0] == b[0]: # separate soup from the rest
        soup.append(a.pop(0))
        b.pop(0)
      a = '\n'.join(a)
      b = '\n'.join(b)
      soup = '\n'.join(soup)
      return (discord.Embed(title=Lunch.getMotd(date), type='rich', color=discord.Color.blue())
          .add_field(name='Leves:', value=soup)
          .add_field(name='A menü:', value=a)
          .add_field(name='B menü:', value=b)
          .set_footer(text='Have fun!'))
    except:
      return discord.Embed(title=Lunch.getMotd(date), type='rich', color=discord.Color.blue(), description=rawlunch) # if lunch formatting failed, just print it out unformatted


  def generateEmbed(date):
    URL = LUNCH_URL.format(date=date.isoformat())
    with urllib.request.urlopen(URL) as response:
      lunch_xml = response.read().decode('utf-8') # get lunchxml
      root = ET.fromstring(lunch_xml) # parse it
      rawlunch = root[2].text # get the relevant part
      if rawlunch == None:
        return None
      return Lunch.format(rawlunch, date)


  async def print(channel, date):
    await channel.trigger_typing()
    lunchEmbed = Lunch.generateEmbed(date)
    if lunchEmbed == None:
      await Util.sendError(channel, 'The lunch for ' + date.isoformat() + ' isn\'t available yet/anymore, or there\'s no lunch on the date specified.')
    else:
      await channel.send(embed=lunchEmbed)


  async def help(channel, args): # lunch
    embed = discord.Embed(title='Available subcommands for lunch:', type='rich',
        description='on HH[:MM]\noff HH[:MM]\ntoday\ntomorrow\nday [[YYYY-]MM-]DD\ninfo', color=discord.Color.blue())
    await channel.send(embed=embed)


  async def on(channel, args): # lunch on
    if len(args) < 1:
      await Util.sendError(channel, 'Please type in a time for the lunch notifications.')
      return
    time = Util.parseTime(args[0])
    if time == None:
      await Util.sendError(channel, 'Please type in a valid time.')
      return
    if Util.setStuff(time, channel, LUNCH, True):
      await Util.sendSuccess(channel, 'You have enabled lunch notifications for this channel! You will get them every day at ' + time.strftime('%H:%M') + '.')
    else:
      await Util.sendError(channel, 'Lunch notifications are already enabled for this channel at ' + time.strftime('%H:%M') + '.')


  async def off(channel, args): # lunch off
    if len(args) < 1:
      await Util.sendError(channel, 'Please type in a time to remove.')
      return
    time = Util.parseTime(args[0])
    if time == None:
      await Util.sendError(channel, 'Please type in a valid time.')
      return
    if Util.setStuff(time, channel, LUNCH, False):
      await Util.sendSuccess(channel, 'You have turned off lunch notifications for this channel at ' + time.strftime('%H:%M') + '.')
    else:
      await Util.sendError(channel, 'There were no lunch notifications scheduled at ' + time.strftime('%H:%M') + ' in this channel.')


  async def info(channel, args): # lunch info
    times = []
    for i in range(len(state[AUTO_SEND])):
      if str(channel.id) in state[AUTO_SEND][i][CHANNELS] and state[AUTO_SEND][i][CHANNELS][str(channel.id)][LUNCH]:
        times.append(Util.timeAt(i).strftime('%H:%M'))
    if len(times) == 0:
      description = 'There aren\'t any lunch notifications set for this channel.'
    elif len(times) == 1:
      description = 'You will get lunch notifications at ' + times[0]
    else:
      description = 'You will get lunch notifications at the following times:\n' + '\n'.join(times)
    embed = discord.Embed(title='Lunch info:', description=description,
        type='rich', color=discord.Color.blue())
    await channel.send(embed=embed)


  async def today(channel, args): # lunch today
    await Lunch.print(channel, datetime.date.today())


  async def tomorrow(channel, args): # $lunch tomorrow
    await Lunch.print(channel, datetime.date.today() + datetime.timedelta(days=1))


  async def day(channel, args): # $lunch day
    if len(args) != 1:
      await Util.sendError(channel, 'Please type in a date for your lunch request.')
      return
    date = Util.parseDate(args[0])
    if date == None:
      await Util.sendError(channel, 'Please type in a valid date.')
      return
    await Lunch.print(channel, date)


class Subst():
  async def help(channel, args):
    embed = discord.Embed(title='Available subcommands for subst:', type='rich',
        description='on [HH[:MM]]\noff [HH[:MM]]\ntoday\ntomorrow\nday [[YYYY-]MM-]DD\ninfo', color=discord.Color.blue())
    await channel.send(embed=embed)


  async def on(channel, args): # TODO add instant notify
    if len(args) < 1:
      await Util.sendError(channel, 'Please type in a time to schedule substitution digests for.')
      return
    time = Util.parseTime(args[0])
    if time == None:
      await Util.sendError(channel, 'Please type in a valid time.')
      return
    if Util.setStuff(time, channel, LUNCH, False):
      await Util.sendSuccess(channel, 'You have enabled scheduled substitution digests for this channel! You will get them every day at ' + time.strftime('%H:%M') + '.')
    else:
      await Util.sendError(channel, 'Scheduled substitution digests are already enabled for this channel at ' + time.strftime('%H:%M') + '.')


  async def off(channel, args): # lunch off
    if len(args) < 1:
      await Util.sendError(channel, 'Please type in a time to remove.')
      return
    time = Util.parseTime(args[0])
    if time == None:
      await Util.sendError(channel, 'Please type in a valid time.')
      return
    if Util.setStuff(time, channel, LUNCH, True):
      await Util.sendSuccess(channel, 'You have turned off scheduled substitution digests for this channel at ' + time.strftime('%H:%M') + '.')
    else:
      await Util.sendError(channel, 'There were no substitution digests scheduled at ' + time.strftime('%H:%M') + ' in this channel.')


  async def info(channel, args):
    times = []
    for i in range(len(state[AUTO_SEND])):
      if str(channel.id) in state[AUTO_SEND][i][CHANNELS] and state[AUTO_SEND][i][CHANNELS][str(channel.id)][SUBST]:
        times.append(Util.timeAt(i).strftime('%H:%M'))
    if len(times) == 0:
      if str(channel.id) in state[AUTO_SUBST]:
        description = 'You will get substitution notifications right when they get on the board.'
      else:
        description = 'Substitution notifications are turned off for this channel.'
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
    embed = discord.Embed(title='Lunch info:', description=description,
        type='rich', color=discord.Color.blue())
    await channel.send(embed=embed)


  async def today(channel, args): # lunch today
    await channel.send(embed=getSubstEmbed(datetime.date.today()))


  async def tomorrow(channel, args): # $lunch tomorrow
    await channel.send(embed=getSubstEmbed(datetime.date.today() + datetime.timedelta(days=1)))


  async def day(channel, args): # $lunch day
    if len(args) != 1:
      await Util.sendError(channel, 'Please type in a date for your substitution request.')
      return
    date = Util.parseDate(args[0])
    if date == None:
      await Util.sendError(channel, 'Please type in a valid date.')
      return
    await channel.send(embed=await getSubstEmbed(date))


async def autoSend():
  now = datetime.datetime.now()
  i = Util.indexOf(now.time())
  print('autoSend started...')
  while True:
    nextTime = datetime.datetime.combine(now.date(), Util.timeAt(i))
    if i == len(state[AUTO_SEND]): # -> next time to send is tomorrow
      i = 0
      nextTime += datetime.timedelta(days=1)
    #TODO check for new substitutes
    if nextTime - now > datetime.timedelta(seconds=30 * 60):
      print('Waiting 30 minutes...')
      await asyncio.sleep(30 * 3600)
      continue
    print((nextTime - now).seconds, 'seconds to the next print.')
    await asyncio.sleep((nextTime - now).seconds)
    print('Printing...')
    now = datetime.datetime.now()
    if now.time() > datetime.time(15, 00): #TODO print substitutions too
      lunchEmbed = Lunch.generateEmbed(datetime.date.today() + datetime.timedelta(days=1))
      #substEmbed = 
    else:
      lunchEmbed = Lunch.generateEmbed(datetime.date.today())
      #substEmbed = 
    for channelID, send in state[AUTO_SEND][i][CHANNELS].items():
      if send[LUNCH] and lunchEmbed != None:
        await client.get_channel(int(channelID)).send(embed=lunchEmbed)
#      if send[SUBST] and substEmbed != none:
#        await client.get_channel(stuff[CHANNEL_ID]).send(embed=subsdEmbed)
    now = datetime.datetime.now()
    i += 1


async def help(channel, args):
  embed = discord.Embed(title='Available commands:', type='rich',
      description='lunch [...]\nsubst [...]\nping [delay]\nplot function\nmention', color=discord.Color.blue())
  await channel.send(embed=embed)


async def ping(channel, args): # ping [delay]
  if len(args) == 1:
    try:
      await asyncio.sleep(int(args[0]))
    except ValueError:
      pass
  await channel.send("pong") 


domain = 10
accuracy = 0.1
async def plot(channel, args): # can throw exception, unhandled for now
  function = ''.join(args)
  plt.close()
  plt.axes((0, 0, 1, 1), frameon=False, aspect='equal')
  plt.ylim(-domain / 2, domain/2)
  x = np.arange(-(domain / 2 + accuracy / 2), (domain / 2 + accuracy / 2), accuracy)
  plt.plot(x, numexpr.evaluate(function))
  plt.plot(x, 0*x, color='black')
  plt.axvline(x=0, color='black')
  buf = io.BytesIO()
  plt.savefig(buf, bbox_inches='tight', format='png')
  buf.seek(0)
  await channel.send("Plot of `{}`:".format(function), file=discord.File(buf, filename="plot.png"))


async def mention(channel, args):
  if channel.id in state[NO_MENTION]:
    state[NO_MENTION].remove(channel.id)
    await Util.sendSuccess(channel, 'Mentioning the bot is now required.')
  else:
    state[NO_MENTION].append(channel.id)
    await Util.sendSuccess(channel, 'Mentioning the bot id now optional.')
  Util.saveState()


commands = {
  '': help,
  ' ': help,
  'help': help,
  'ping': ping,
  'plot': plot,
  'mention': mention, }

commandsWSub = {
  'lunch': Lunch,
  'subst': Subst, }

subCommands = [
  'help',
  'on',
  'off',
  'info',
  'today',
  'tomorrow',
  'day', ]


@client.event
async def on_ready():
  global autoSendTask
  if autoSendTask == None and len(state[AUTO_SEND]) > 0:
    autoSendTask = client.loop.create_task(autoSend())
  print('Ready!')


@client.event
async def on_message(message):
  channel = message.channel
  if message.author == client.user or not (client.user in message.mentions or type(channel) == discord.channel.DMChannel or channel.id in state[NO_MENTION]):
    return
  splitMessage = message.content.split(' ')
  if client.user in message.mentions:
    splitMessage.pop(0)
  if splitMessage[0] in commands:
    args = splitMessage[1:]
    await commands[splitMessage[0]](channel, args) # run the command
    return
  elif splitMessage[0] in commandsWSub:
    if len(splitMessage) == 1:
      await getattr(commandsWSub[splitMessage[0]], 'help')(channel, [])
      return
    elif splitMessage[1] in subCommands:
      args = splitMessage[2:]
      await getattr(commandsWSub[splitMessage[0]], splitMessage[1])(channel, args)
      return
  if client.user in message.mentions:
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

