import discord
import datetime
import json
import asyncio

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

client = discord.Client()
autoSendTask = None
global state
state = {AUTO_SEND:[], AUTO_SUBST:[], CLASSOF:{}, COUNTDOWN:{}, NO_MENTION:[], KNOWN_SUBSTS:[]}
## state: {AUTO_SEND:[{ISOTIME:isotime, CHANNELS:{channelId:{LUNCH:bool, SUBST:bool}, ...}}, ...], AUTO_SUBST:[channelID, ...], CLASSOF:{channelId:class, ...}, COUNTDOWN:{channelId:msgId, ...}, KNOWN_SUBSTS:[]}

class Util():
  stateFile = 'state.json'

  def timeAt(index) -> datetime.time:
    global state
    if len(state[AUTO_SEND]) == 0:
      return None
    else:
      return datetime.time.fromisoformat(state[AUTO_SEND][index % len(state[AUTO_SEND])][ISOTIME])

  def indexOf(time) -> int: 
    global state
    if len(state[AUTO_SEND]) == 0:
      return 0
    bot = 0
    top = len(state[AUTO_SEND]) - 1
    if time < Util.timeAt(bot) or Util.timeAt(top) < time:
      return 0
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

  def startAutoSend():
    global state
    global autoSendTask
    if autoSendTask != None:
      autoSendTask.cancel()
      autoSendTask = None
      print('autoSend stopped.')
    if len(state[AUTO_SEND]) > 0 or len(state[AUTO_SUBST]) > 0:
      autoSendTask = client.loop.create_task(Util.autoSend())

  def setStuff(time, channel, thingToSet, to): # TODO find a better name for this too
    global state
    index = Util.indexOf(time)
    strID = str(channel.id)
    changed = True
    if index < len(state[AUTO_SEND]) and state[AUTO_SEND][index][ISOTIME] == time.isoformat():
      if not strID in state[AUTO_SEND][index][CHANNELS]:
        state[AUTO_SEND][index][CHANNELS].append({strID:{LUNCH:False, SUBST:False}})
    else:
      state[AUTO_SEND].insert(index, {ISOTIME:time.isoformat(), CHANNELS:{strID:{LUNCH:False, SUBST:False}}})
    if state[AUTO_SEND][index][CHANNELS][strID][thingToSet] == to:
      changed = False
    state[AUTO_SEND][index][CHANNELS][strID][thingToSet] = to
    if not (state[AUTO_SEND][index][CHANNELS][strID][LUNCH] or state[AUTO_SEND][index][CHANNELS][strID][SUBST]):
      state[AUTO_SEND][index][CHANNELS].pop(strID)
      if len(state[AUTO_SEND][index][CHANNELS]) == 0:
        state[AUTO_SEND].pop(index)
    if changed:
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
    global state
    with open(Util.stateFile, 'w') as f: # open file for writing
      json.dump(state, f)

  def loadState(): # import schedules saved in jsons
    global state
    try:
      with open(Util.stateFile, 'r') as f: # open file for reading
        state = json.load(f)
    except FileNotFoundError:
      pass
    except json.decoder.JSONDecodeError as e:
      print('Invalid state.json!')
      print(e.msg)

