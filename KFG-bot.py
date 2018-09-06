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
## state: {AUTO_SEND:[{ISOTIME:isotime, CHANNEL_IDS:[{CHANNEL_ID:channelId, SEND_LUNCH:bool, SEND_SUBST:bool}, ...]}, ...], AUTO_SUBST:[channelID, ...], CLASSOF:{channelId:class, ...}, COUNTDOWN:[{CHANNEL_ID:channelId, MSG_ID:msgId}, ...]}
AUTO_SEND = 'autoSend'
AUTO_SUBST = 'autoSubst'
CLASSOF = 'classOf'
COUNTDOWN = 'countdown'
ISOTIME = 'isotime'
CHANNEL_IDS = 'channelIDs'
CHANNEL_ID = 'channelID'
SEND_LUNCH = 'sendLunch'
SEND_SUBST = 'sendSubst'
MSG_ID = 'msgID'


def saveState(): # export current state to state.json
  stateFile = open(STATE_FILE, 'w') # open file for writing
  json.dump(state, stateFile)
  stateFile.close()


def loadState(): # import schedules saved in jsons
  global stat
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


async def help(channel, args):
  embed = discord.Embed(title='Available commands:', type='rich',
      description='lunch [...]\nsubst [...]\nping [delay [DELAY]]', color=discord.Color.blue())
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
  menu_xml = urllib.request.urlopen(LUNCH_URL.format(date=date)).read().decode('utf-8') # get menu as an xml
  root = ET.fromstring(menu_xml) # parse it
  rawlunch = root[2].text # get the relevant part
  if rawlunch == None:
    return None
  return formatLunch(rawlunch, date)


def getTime(index):
  return datetime.time.fromisoformat(state[AUTO_SEND][index][ISOTIME])


def getIndex(time): 
  bot = 0
  top = len(state[AUTO_SEND]) - 1
  if time < getTime(bot):
    return bot
  if getTime(top) < time:
    return top + 1
  while True:
    avg = (top + bot) / 2
    if getTime(avg) == time:
      return avg
    elif getTime(avg) < time:
      top = avg
    else:
      bot = avg
    if top - bot == 1:
      return top


async def autoSend(): #TODO most certainly needs fixing
  i = getIndex(datetime.datetime.now())
  while True:
    now = datetime.datetime.now()
    nextTime = datetime.datetime.combine(datetime.today(), getTime(i))
    if i == len(state[AUTO_SEND]):
      i = 0
      nextTime += datetime.timedelta(days=1)
    #TODO check for new substitutes
    if nextTime - now > datetime.timedelta(seconds=30*3600):
      await asyncio.sleep(30*3600)
      continue
    await asyncio.sleep((nextTime - now).seconds)
    now = datetime.datetime.now()
    if now.time() > datetime.time(15, 00): #TODO print substitutions too
      menuEmbed = getMenuEmbed(datetime.date.today() + datetime.timedelta(days=1))
      #substEmbed = 
    else:
      menuEmbed = getMenuEmbed(datetime.date.today())
      #substEmbed = 
    for stuff in state[AUTO_SEND][i]: #TODO find a better name for stuff
      if stuff[SEND_LUNCH] and menuEmbed != None:
        await client.get_channel(stuff[CHANNEL_ID]).send(embed=menuEmbed)
#      if stuff[SEND_SUBST] and substEmbed != none:
#        await client.get_channel(stuff[CHANNEL_ID]).send(embed=subsdEmbed)
    i += 1

async def lunchHelp(channel, args): # lunch
  embed = discord.Embed(title='Available subcommands for lunch:', type='rich',
      description='on HH[:MM]\noff HH[:MM]\ntoday\ntomorrow\nday [[YYYY-]MM-]DD\ninfo', color=discord.Color.blue())
  await channel.send(embd=embed)


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


def setStuff(time, *, sendLunch=None, sendSubst=None): # TODO find a better name for this too
  index = getIndex(time)
  if index = len(state[AUTO_SEND]):
    state[AUTO_SEND].append({CHANNEL_ID = channel.id, SEND_LUNCH = bool(sendLunch), SEND_SUBST = bool(sendSubst)})
  else:
    if state[AUTO_SEND][index][ISOTIME] == time.isoformat():
      for i in range(len(state[AUTO_SEND][index][CHANNEL_IDS])):
        if state[AUTO_SEND][index][CHANNEL_IDS][i][CHANNEL_ID] == channel.id:
          if state[AUTO_SEND][index][CHANNEL_IDS][i][SEND_LUNCH]:
            sendMsgError(channel, 'lunch notifications are already enabled for ' + time.strftime('%H:%M') + '!')
            return
          else:
            state[AUTO_SEND][index][CHANNEL_IDS][i][SEND_LUNCH] = True
      if i == len(state[AUTO_SEND][index][CHANNEL_IDS]):
        state[AUTO_SEND][index][CHANNEL_IDS].append({CHANNEL_ID:channel.id, SEND_LUNCH:True, SEND_SUBST:False})
    else:
      state[AUTO_SEND].insert(index, {ISOTIME:time.isoformat(), CHANNEL_IDS:[{CHANNEL_ID:channel.id, SEND_LUNCH:True, SEND_SUBST:False}})
  save_state()
  if autoSendTask != None:
    autoSendTask.cancel()
  autoSendTask = client.loop.create_task(autoSend())


async def lunchOn(channel, args): # lunch on
  if len(args) < 1:
    await sendMsgError(channel, 'Please type in a time for the lunch notifications!')
    return
  global autoSendTask 
  time = getTime(args[0])
  if time == None:
    await sendMsgError(channel, 'Please type in a valid time.')
    return
  await sendMsgSuccess(channel, 'You have enabled lunch notifications for this channel! You will get them every day at ' + time.strftime('%H:%M'))


async def lunchOff(channel, args): # lunch off
  if len(args) < 1:
    await sendMsgError(channel, 'Please type in a time to remove!')
    return
  global autoSendTask 
  time = args[0]
  try:
    hour = int(time.split(':')[0])
    if len(time.split(':')) == 2:
      minute = int(time.split(':')[1])
    else: minute = 0
    time = datetime.time(hour, minute)
  except ValueError:
    await sendMsgError(channel, 'Please type in a valid time')
    return
  for i_time in range(len(schedule)): #TODO this is prolly bullshit too
    if schedule[i_time][TIME] == time:
      if channel in schedule[i_time][CHANNELS]:
        schedule[i_time][CHANNELS].remove(channel)
        if len(schedule[i_time][CHANNELS]) == 0:
          schedule.pop(i_time)
        autoSendTask.cancel()
        if len(schedule) > 0:
          autoSendTask = client.loop.create_task(daily_lunch())
        await sendMsgSuccess(channel, 'You have turned off lunch notifications for this channel at ' + time.strftime('%H:%M') + '!')
        save_state()
        return
      else:
        break
  await sendMsgError(channel, 'There wasn\'t a lunch notification scheduled at ' + time.strftime('%H:%M') + ' in this channel!\nTry $lunch info.')


async def lunchInfo(channel, args): # lunch info
  times = []
  for i in range(len(schedule)):
    if channel.id in schedule[i][CHANNELS]:
      times.append(datetime.time.fromisoformat(schedule[i][TIME]).strftime('%H:%M'))
  if len(times) == 0:
    description = 'There aren\'t any lunch notifications set for this channel.'
  elif len(times) == 1:
    description = 'You will get lunch notifications at ' + times[0]
  else:
    description = 'You will get lunch notifications at the following times:\n' + '\n'.join(times)
  embed = discord.Embed(title='Lunch info:', description=description,
      type='rich', color=discord.Color.blue())
  await channel.send(embed=embed)


async def lunchToday(channel, args): # lunch today
    await printMenu([channel.id], datetime.date.today())


async def lunchTomorrow(channel, args): # $lunch tomorrow
    await printMenu([channel.id], datetime.date.today() + datetime.timedelta(days=1))


async def lunchDay(channel, args): # $lunch day
  if len(args) != 1:
    await sendMsgError(channel, 'Please type in a date for your lunch request!')
    return
  date = args[0]
  try:
    date = date.split('-')
    day = int(date[len(date) - 1])
    if len(date) >= 2:
      month = int(date[len(date) - 2])
    else:
      month = datetime.date.today().month
    if len(date) == 3:
      year = int(date[0])
    else:
      year = datetime.date.today().year
    date = datetime.date(year, month, day)
  except ValueError:
    await sendMsgError(channel, 'Please type in a valid date!')
    return
  await printMenu([channel.id], date)


async def substHelp(channel, args):
  embed = discord.Embed(title='Available subcommands for subst:', type='rich',
      description='on [HH[:MM]]\noff [HH[:MM]]\ntoday\ntomorrow\nday [[YYYY-]MM-]DD\ninfo', color=discord.Color.blue())
  await channel.send(embed=embed)


async def substOn(channel, args):
  if len(args) == 0:
    return
  global autoSendTask 
  time = args[0]
  try:
    hour = int(time.split(':')[0])
    if len(time.split(':')) == 2:
      minute = int(time.split(':')[1])
    else:
      minute = 0
    time = datetime.time(hour, minute)
  except ValueError:
    await sendMsgError(channel, 'Please type in a valid time')
    return
  if len(schedule) == 0: #TODO this thing is complete bullshit
    schedule.append({TIME:time, CHANNELS:[channel]})
  else:
    for i_time in range(len(schedule)):
      if schedule[i_time][TIME] == time:
        if not channel in schedule[i_time][CHANNELS]:
          schedule[i_tme][CHANNELS].append(cahnnel)
        break
      if schedule[i_time][TIME] > time:
        schedule.insert(i_time, {TIME:time, CHANNELS:[channel]})
        break
      if i_time == len(schedule) - 1:
        schedule.append({TIME:time, CHANNELS:[channel]})
        break
  save_state()
  if autoSendTask != None:
    autoSendTask.cancel()
  autoSendTask = client.loop.create_task(autoSend())
  await sendMsgSuccess(channel, 'You have enabled lunch notifications for this channel! You will get them every day at ' + time.strftime('%H:%M'))


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
  if autoSendTask == None and len(schedule) > 0:
    autoSendTask = client.loop.create_task(autoSend())
  print('Ready!')


commands = {
  '': help,
  'help': help,
  'lunch': lunchHelp,
  'lunch help': lunchHelp,
  'lunch on': lunchOn,
  'lunch off': lunchOff,
  'lunch info': lunchInfo,
  'lunch today': lunchToday,
  'lunch tomorrow': lunchTomorrow,
  'lunch day': lunchDay,
  'ping': ping }
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


#async def print_substitutions(channel_ids, user, date):
#    if date == datetime.date.today():
#        if datetime.datetime.now().time() > datetime.time(16, 00):
#            motd = 'Today\'s substitutions for class {} were:'
#        else:
#            motd = 'Here are today\'s substitutions for class {}:'
#    elif date == datetime.date.today() + datetime.timedelta(days = 1):
#        motd = 'Substitutions tomorrow for class {} will be:'
#    elif date < datetime.date.today():
#        motd = 'Substitutions on for class {} ' + date.isoformat() + ' were:'
#    else:
#        motd = 'Substitutions for class {} on ' + date.isoformat() + ' will be:'
#    for channel_id in channel_ids:
#        await client.send_typing(client.get_channel(channel_id))
#    substitutions_json = urllib.request.urlopen('https://apps.karinthy.hu/helyettesites/json.php?day=' + date.isoformat()).read().decode('utf-8')
#    substitutions_list = json.loads(substitutions_json)[0]['entries']
#    substitutions_for_classes = { channel_id:filter(lambda entry: entry['class'] == substitutions_schedule[CLASSINFO][channel_id], substitutions_list) for cannel_id in channel_ids }
#    for channel_id in channel_ids:
#        pass


#        elif command[0] == '$subs' and False:
#            if len(command) == 1:
#                embed = discord.Embed(title='Available commands for $subs:', type='rich', description='on morning or evening\noff morning or evening\ntoday\ntomorrow\nnext\nday YYYY-MM-DD or MM-DD or DD\ninfo', color=discord.Color.blue())
#                await channel.send(author.mention, embed=embed)
#            elif command[1] == 'on':
#                if len(command) == 2 or not command[2] in [MORNING, EVENING]:
#                    if channel.id in substitutions_schedule[CLASSINFO]:
#                        embed = discord.Embed(title='Error!', description='Please enter morning or evening.', type='rich', color=discord.Color.red())
#                        await channel.send(author.mention, embed=embed)
#                    else:
#                        embed = discord.Embed(title='Error!', description='Please enter morning or evening and a classID.', type='rich', color=discord.Color.red())
#                        await channel.send(author.mention, embed=embed)
#                elif len(command) == 3 and not channel.id in substitutions_schedule[CLASSINFO]: 
#                    embed = discord.Embed(title='Error!', description='Please enter a classID.', type='rich', color=discord.Color.red())
#                    await channel.send(author.mention, embed=embed)
#                elif channel in substitutions_schedule[command[2]]:
#                    embed = discord.Embed(title='Error!', description='Substitution notifications are already turned on in the ' + command[2] + ' for this channel.', type='rich', color=discord.Color.red())
#                    await channel.send(author.mention, embed=embed)
#                else:
#                    pass


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

