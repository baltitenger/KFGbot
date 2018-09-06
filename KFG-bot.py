#!/usr/bin/python3 -u

import discord
import asyncio
import datetime
import urllib.request
import xml.etree.ElementTree as ET
import json
import signal


def sigterm_handler(signal, stackframe):
  raise KeyboardInterrupt
signal.signal(signal.SIGTERM, sigterm_handler) # graceful stop


client = discord.client.Client()
autoSendTask = None


# constants
LUNCH_URL = 'https://naplo.karinthy.hu/app/interface.php?view=v_canteen_export&day={date!s}' 
SUBST_URL = 'https://admin.karinthy.hu/api/substitutions?day={date!s}'
STATE_FILE = 'state.json'
## state: {AUTO_SEND:[{ISOTIME:isotime, CHANNELS:{channelId:{LUNCH:bool, SUBST:bool}, ...}}, ...], AUTO_SUBST:[channelID, ...], CLASSOF:{channelId:class, ...}, COUNTDOWN:{channelId:msgId, ...}}
AUTO_SEND = 'autoSend'
AUTO_SUBST = 'autoSubst'
CLASSOF = 'classOf'
COUNTDOWN = 'countdown'
ISOTIME = 'isotime'
CHANNELS = 'channelIDs'
LUNCH = 'lunch'
SUBST = 'subst'
state = {AUTO_SEND:[], AUTO_SUBST:[], CLASSOF:{}, COUNTDOWN:{}}


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
    print('Invalid ' + e.doc + ' file!')
    print(e.msg)


async def sendMsgSuccess(channel, message):
  embed = discord.Embed(title='Success!', type='rich', color=discord.Color.green(), description=message)
  await channel.send(embed=embed)


async def sendMsgError(channel, message):
  embed = discord.Embed(title='Error!', type='rich', color=discord.Color.red(), description=message)
  await channel.send(embed=embed)


def getLunchMotd(date): # get lunch motd depending on date queried
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
  

def formatLunch(rawlunch, date):
  try:
    lunch = rawlunch.split('\n\n')
    aMenu = lunch[0].split('\n')[1:]
    bMenu = lunch[1].split('\n')[1:]
    soup = []
    while aMenu[0] == bMenu[0]: # separate soup from the rest
      soup.append(aMenu.pop(0))
      bMenu.pop(0)
    aMenu = '\n'.join(aMenu)
    bMenu = '\n'.join(bMenu)
    soup = '\n'.join(soup)
    return (discord.Embed(title=getLunchMotd(date), type='rich', color=discord.Color.blue())
        .add_field(name='Leves:', value=soup)
        .add_field(name='A menü:', value=aMenu)
        .add_field(name='B menü:', value=bMenu)
        .set_footer(text='Have fun!'))
  except:
    return discord.Embed(title=getLunchMotd(date), type='rich', color=discord.Color.blue(), description=rawlunch) # if lunch formatting failed, just print it out unformatted


def getMenuEmbed(date):
  menu_xml = urllib.request.urlopen(LUNCH_URL.format(date=date.isoformat())).read().decode('utf-8') # get menu as an xml
  root = ET.fromstring(menu_xml) # parse it
  rawlunch = root[2].text # get the relevant part
  if rawlunch == None:
    return None
  return formatLunch(rawlunch, date)


def getTime(index):
  if len(state[AUTO_SEND]) == 0:
    return None
  else:
    return datetime.time.fromisoformat(state[AUTO_SEND][index % len(state[AUTO_SEND])][ISOTIME])


def getIndex(time): 
  if len(state[AUTO_SEND]) == 0:
    return 0
  bot = 0
  top = len(state[AUTO_SEND]) - 1
  if time < getTime(bot):
    return bot
  if getTime(top) < time:
    return top + 1
  while True:
    avg = (top + bot) // 2
    if getTime(avg) == time:
      return avg
    elif getTime(avg) < time:
      bot = avg
    else:
      top = avg
    if top - bot == 1:
      return top


async def autoSend(): #TODO needs redoing
  i = getIndex(datetime.datetime.now().time())
  while True:
    now = datetime.datetime.now()
    if i == len(state[AUTO_SEND]):
      i = 0
      nextTime = datetime.datetime.combine(datetime.date.today(), getTime(i))
      nextTime += datetime.timedelta(days=1)
    else:
      nextTime = datetime.datetime.combine(datetime.date.today(), getTime(i))
    #TODO check for new substitutes
    if nextTime - now > datetime.timedelta(seconds=30 * 3600):
      await asyncio.sleep(30 * 3600)
      continue
    await asyncio.sleep((nextTime - now).seconds)
    now = datetime.datetime.now()
    if now.time() > datetime.time(15, 00): #TODO print substitutions too
      menuEmbed = getMenuEmbed(datetime.date.today() + datetime.timedelta(days=1))
      #substEmbed = 
    else:
      menuEmbed = getMenuEmbed(datetime.date.today())
      #substEmbed = 
    for channelID, send in state[AUTO_SEND][i][CHANNELS].items():
      if send[LUNCH] and menuEmbed != None:
        await client.get_channel(channelID).send(embed=menuEmbed)
#      if send[SUBST] and substEmbed != none:
#        await client.get_channel(stuff[CHANNEL_ID]).send(embed=subsdEmbed)
    i += 1


async def help(channel, args):
  embed = discord.Embed(title='Available commands:', type='rich',
      description='lunch [...]\nsubst [...]\nping [delay [DELAY]]', color=discord.Color.blue())
  await channel.send(embed=embed)


async def lunchHelp(channel, args): # lunch
  embed = discord.Embed(title='Available subcommands for lunch:', type='rich',
      description='on HH[:MM]\noff HH[:MM]\ntoday\ntomorrow\nday [[YYYY-]MM-]DD\ninfo', color=discord.Color.blue())
  await channel.send(embd=embed)


async def substHelp(channel, args):
  embed = discord.Embed(title='Available subcommands for subst:', type='rich',
      description='on [HH[:MM]]\noff [HH[:MM]]\ntoday\ntomorrow\nday [[YYYY-]MM-]DD\ninfo', color=discord.Color.blue())
  await channel.send(embed=embed)


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


def setStuff(time, channel, thingToSet, to): # TODO find a better name for this too
  index = getIndex(time)
  if index < len(state[AUTO_SEND]) and state[AUTO_SEND][index][ISOTIME] == time.isoformat():
    if str(channel.id) in state[AUTO_SEND][index][CHANNELS]:
      if state[AUTO_SEND][index][CHANNELS][str(channel.id)][thingToSet] == to:
        return False
      else:
        state[AUTO_SEND][index][CHANNELS][str(channel.id)][thingToSet] = to
    else:
      state[AUTO_SEND][index][CHANNELS].append({str(channel.id):{LUNCH:False, SUBST:False}})
  else:
    state[AUTO_SEND].insert(index, {ISOTIME:time.isoformat(), CHANNELS:{str(channel.id):{LUNCH:False, SUBST:False}}})
  state[AUTO_SEND][index][CHANNELS][str(channel.id)][thingToSet] = to
  if not (state[AUTO_SEND][index][CHANNELS][str(channel.id)][LUNCH] or state[AUTO_SEND][index][CHANNELS][str(channel.id)][SUBST]):
    state[AUTO_SEND][index][CHANNELS].pop(str(channel.id))
    if len(state[AUTO_SEND][index][CHANNELS]) == 0:
      state[AUTO_SEND].pop(index)
  saveState()
  global autoSendTask
  if autoSendTask != None:
    autoSendTask.cancel()
  if len(state[AUTO_SEND]) > 0:
    autoSendTask = client.loop.create_task(autoSend())
  return True


async def lunchOn(channel, args): # lunch on
  if len(args) < 1:
    await sendMsgError(channel, 'Please type in a time for the lunch notifications.')
    return
  time = parseTime(args[0])
  if time == None:
    await sendMsgError(channel, 'Please type in a valid time.')
    return
  if setStuff(time, channel, LUNCH, True):
    await sendMsgSuccess(channel, 'You have enabled lunch notifications for this channel! You will get them every day at ' + time.strftime('%H:%M') + '.')
  else:
    await sendMsgError(channel, 'Lunch notifications are already enabled for this channel at ' + time.strftime('%H:%M') + '.')


async def lunchOff(channel, args): # lunch off
  if len(args) < 1:
    await sendMsgError(channel, 'Please type in a time to remove.')
    return
  time = parseTime(args[0])
  if time == None:
    await sendMsgError(channel, 'Please type in a valid time.')
    return
  if setStuff(time, channel, LUNCH, False):
    await sendMsgSuccess(channel, 'You have turned off lunch notifications for this channel at ' + time.strftime('%H:%M') + '.')
  else:
    await sendMsgError(channel, 'There were no lunch notifications scheduled at ' + time.strftime('%H:%M') + ' in this channel.')


async def substOn(channel, args): # TODO add instant notify
  if len(args) < 1:
    await sendMsgError(channel, 'Please type in a time to schedule substitution digests for.')
    return
  time = parseTime(args[0])
  if time == None:
    await sendMsgError(channel, 'Please type in a valid time.')
    return
  if setStuff(time, channel, LUNCH, False):
    await sendMsgSuccess(channel, 'You have enabled scheduled substitution digests for this channel! You will get them every day at ' + time.strftime('%H:%M') + '.')
  else:
    await sendMsgError(channel, 'Scheduled substitution digests are already enabled for this channel at ' + time.strftime('%H:%M') + '.')


async def substOff(channel, args): # lunch off
  if len(args) < 1:
    await sendMsgError(channel, 'Please type in a time to remove.')
    return
  time = parseTime(args[0])
  if time == None:
    await sendMsgError(channel, 'Please type in a valid time.')
    return
  if setStuff(time, channel, LUNCH, True):
    await sendMsgSuccess(channel, 'You have turned off scheduled substitution digests for this channel at ' + time.strftime('%H:%M') + '.')
  else:
    await sendMsgError(channel, 'There were no substitution digests scheduled at ' + time.strftime('%H:%M') + ' in this channel.')


async def lunchInfo(channel, args): # lunch info
  times = []
  for i in range(len(state[AUTO_SEND])):
    if str(channel.id) in state[AUTO_SEND][i][CHANNELS] and state[AUTO_SEND][i][CHANNELS][str(channel.id)][LUNCH]:
      times.append(getTime(i).strftime('%H:%M'))
  if len(times) == 0:
    description = 'There aren\'t any lunch notifications set for this channel.'
  elif len(times) == 1:
    description = 'You will get lunch notifications at ' + times[0]
  else:
    description = 'You will get lunch notifications at the following times:\n' + '\n'.join(times)
  embed = discord.Embed(title='Lunch info:', description=description,
      type='rich', color=discord.Color.blue())
  await channel.send(embed=embed)


async def substInfo(channel, args):
  times = []
  for i in range(len(state[AUTO_SEND])):
    if str(channel.id) in state[AUTO_SEND][i][CHANNELS] and state[AUTO_SEND][i][CHANNELS][str(channel.id)][SUBST]:
      times.append(getTime(i).strftime('%H:%M'))
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


async def printLunch(channel, date):
  menuEmbed = getMenuEmbed(date)
  if menuEmbed == None:
    await sendMsgError(channel, 'The lunch for ' + date.isoformat() + 'isn\'t available yet/anymore, or there\'s no lunch on the date specified.')
  else:
    await channel.send(embed=menuEmbed)


async def lunchToday(channel, args): # lunch today
  await printLunch(channel, datetime.datetime.today)


async def substToday(channel, args): # lunch today
  await channel.send(embed=getSubstEmbed(datetime.date.today()))


async def lunchTomorrow(channel, args): # $lunch tomorrow
  await printLunch(channel, datetime.date.today() + datetime.timedelta(days=1))


async def substTomorrow(channel, args): # $lunch tomorrow
  await channel.send(embed=getSubstEmbed(datetime.date.today() + datetime.timedelta(days=1)))


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


async def lunchDay(channel, args): # $lunch day
  if len(args) != 1:
    await sendMsgError(channel, 'Please type in a date for your lunch request.')
    return
  date = parseDate(args[0])
  if date == None:
    await sendMsgError(channel, 'Please type in a valid date.')
    return
  await printLunch(channel, date)


async def substDay(channel, args): # $lunch day
  if len(args) != 1:
    await sendMsgError(channel, 'Please type in a date for your substitution request.')
    return
  date = parseDate(args[0])
  if date == None:
    await sendMsgError(channel, 'Please type in a valid date.')
    return
  await channel.send(embed=await getSubstEmbed(date))


async def ping(channel, args): # ping [delay]
  if len(args) == 1:
    try:
      await asyncio.sleep(int(args[0]))
    except ValueError:
      pass
  await channel.send("pong") 


@client.event
async def on_ready():
  global autoSendTask
  if autoSendTask == None and len(state[AUTO_SEND]) > 0:
    autoSendTask = client.loop.create_task(autoSend())
  print('Ready!')


commands = {
  '': help,
  ' ': help,
  'help': help,
  'lunch': lunchHelp,
  'lunch help': lunchHelp,
  'subst': substHelp,
  'subst help': substHelp,
  'lunch on': lunchOn,
  'subst on': substOn,
  'lunch off': lunchOff,
  'subst off': substOff,
  'lunch info': lunchInfo,
  'subst info': substInfo,
  'lunch today': lunchToday,
  'subst today': substToday,
  'lunch tomorrow': lunchTomorrow,
  'subst tomorrow': substTomorrow,
  'lunch day': lunchDay,
  'subst day': substDay,
  'ping': ping,
  'ping delay': ping }


@client.event
async def on_message(message):
  if not client.user in message.mentions:
    return
  command = ' '.join(message.content.split(' ')[1:3])
  args = message.content.split(' ')[3:]
  channel = message.channel
  if command in commands: # check if message is a command
    await channel.trigger_typing()
    await commands[command](channel, args) # run the command
  else:
    await sendMsgError(channel, 'Unknown command.')


print('Starting...')

loadState()

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

