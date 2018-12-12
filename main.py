#!/usr/bin/python3 -u

import discord
import asyncio
import datetime
import os.path

from util import *
from lunch import Lunch
from subst import Subst
from plot import Plot
# from homework import Homework

#TODO nyelvorak?

UPDATE_INTERVAL = 10 * 60 # seconds

async def autoSend(): # TODO fucked up this whole thing
  global state
  i = Util.indexOf(datetime.datetime.now().time())
  justChecking = True
  nextTime = datetime.datetime.combine(datetime.date.today(), Util.timeAt(i))
  if nextTime - datetime.datetime.now() < datetime.timedelta():
    nextTime += datetime.timedelta(days=1)
  ++i
  print('autoSend started...')
  while True:
    now = datetime.datetime.now()
    date = now.date()
    if now.time() > datetime.time(15, 00):
      date += datetime.timedelta(days=1)
    substs = await Subst.acquire(date)
    if justChecking:
      stuff = [ (channelID, {LUNCH: False, SUBST: True}) for channelID in state[AUTO_SUBST]]
    else:
      print(1)
      lunchEmbed = Lunch.format(await Lunch.acquire(date), date)
      print(2)
      print(state)
      stuff = state[AUTO_SEND][i][CHANNELS].items()
      print(3)
      i = i + 1 % len(state[AUTO_SEND])
      print(4)
      nextTime = datetime.datetime.combine(date, Util.timeAt(i))
      print(5)
      if nextTime - now < datetime.timedelta():
        nextTime += datetime.timedelta(days=1)
      print('Printing...')
    for channelID, send in stuff:
      if send[LUNCH] and lunchEmbed != None:
        await client.get_channel(int(channelID)).send(embed=lunchEmbed)
      if send[SUBST] and substs != None:
        substEmbed = Subst.format(substs, channelID, justChecking)
        if substEmbed != None:
          await client.get_channel(int(channelID)).send(embed=substEmbed)
    if justChecking:
      state[KNOWN_SUBSTS] = substs
    justChecking = nextTime - now > datetime.timedelta(seconds=UPDATE_INTERVAL)
    if justChecking:
      await asyncio.sleep(UPDATE_INTERVAL)
    else:
      await asyncio.sleep((nextTime - now).seconds)

Util.autoSend = autoSend

# Commands:
async def help(channel: discord.TextChannel, args):
  """help
  Print help."""
  helpEmbed = discord.Embed(title='Available commands:', type='rich', color=discord.Color.blue())
  for command in commands.values():
    doc = command.__doc__.splitlines()
    helpEmbed.add_field(name=doc[0], value='\n'.join(doc[1:]))
  await channel.send(embed=helpEmbed)

async def ping(channel: discord.TextChannel, args): # ping [delay]
  """ping [delay]
  Reply with `pong` after [delay] seconds."""
  if len(args) == 1:
    try:
      await asyncio.sleep(int(args[0]))
    except ValueError:
      pass
  await channel.send("pong") 

async def mention(channel: discord.TextChannel, args):
  """mention
  toggles optional/recquired mentioning the bot."""
  if str(channel.id) in state[NO_MENTION]:
    state[NO_MENTION].remove(str(channel.id))
    await Util.sendSuccess(channel, 'Mentioning the bot is now required.')
  else:
    state[NO_MENTION].append(str(channel.id))
    await Util.sendSuccess(channel, 'Mentioning the bot is now optional.')
  Util.saveState()

commands = {
  'help': help,
  'ping': ping,
  'mention': mention,
  'lunch': Lunch,
  'subst': Subst,
  'plot': Plot.plot,
#  'hw': HomeWork,
  }


# Events:
@client.event
async def on_ready():
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
  if splitMessage[0] == "dev":
    if dev:
      splitMessage.pop(0);
    else:
      return;
  elif dev:
    return;
  found = False
  if splitMessage[0] in commands:
    command = commands[splitMessage[0]]
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

@client.event
async def on_reaction_add(reaction, user):
  await Plot.updatePlot(reaction, user)

@client.event
async def on_reaction_remove(reaction, user):
  await Plot.updatePlot(reaction, user)


if os.path.isfile("dev"):
  dev = True;
  print('Starting in dev mode...');
else:
  dev = False;
  print('Starting...');

Util.loadState()

try:
  with open('token') as f:
    token = f.readline().strip()
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

