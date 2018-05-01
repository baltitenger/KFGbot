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

signal.signal(signal.SIGTERM, sigterm_handler)

client = discord.client.Client()

daily_lunch_task = None
TIME = 'time'
CHANNELS = 'channels'
lunch_ch = [] # [{TIME:time, CHANNELS[channels]}]

MORNING = 'morning'
EVENING = 'evening'
CLASSINFO = 'classinfo'
CHANNEL = 'channel'
CLASS = 'class'
substitutions_ch = {MORNING:[], EVENING:[], CLASSINFO:{}} # {MORNING:[channels], EVENING:[channels], CLASSINFO:{channel_ids:class_ids}}


def save_list(listname):
    if listname == 'lunch':
        lunch_file = open('lunch_ch.json', 'w')
        lunch_ch_dumpable = [{
            TIME:{'hour':i[TIME].hour, 'minute':i[TIME].minute},
            CHANNELS:[ channel.id for channel in i[CHANNELS] ]}
            for i in lunch_ch]
        json.dump(lunch_ch_dumpable, lunch_file)
        lunch_file.close()
    else:
        substitutions_file = open('substitutions_ch.json', 'w')
        substitutions_ch_dumpable = {
            MORNING:[ channel.id for channel in substitutions_ch[MORNING] ],
            EVENING:[ channel.id for channel in substitutions_ch[EVENING] ],
            CLASSINFO:substitutions_ch[CLASSINFO] }
        json.dump(substitutions_ch_dumpable, substitutions_file)
        substitutions_file.close()

def load_list(listname):
    if listname == 'lunch':
        global lunch_ch
        try:
            lunch_file = open('lunch_ch.json', 'r')
            lunch_ch_dumped = json.load(lunch_file)
            lunch_file.close()
            lunch_ch = [ {
                TIME:datetime.time(i[TIME]['hour'], i[TIME]['minute']),
                CHANNELS:[ client.get_channel(channel_id) for channel_id in i[CHANNELS] ] }
                for i in lunch_ch_dumped ]

        except FileNotFoundError:
            pass
        except json.decoder.JSONDecodeError:
            print('Invalid lunch_ch.json file!')
            open('lunch_ch.json', 'w').close()
    else:
        global substitutions_ch
        try:
            substitutions_file = open('substitutions_ch.json', 'r')
            substitutions_ch_dumped = json.load(substitutions_file)
            substitutions_file.close()
            substitutions_ch = {
            MORNING:[ client.get_channel(channel_id) for channel_id in substitutions_ch_dumped[MORNING] ],
            EVENING:[ client.get_channel(channel_id) for channel_id in substitutions_ch_dumped[EVENING] ],
            CLASSINFO:substitutions_ch_dumped[CLASSINFO] }
        except FileNotFoundError:
            pass
        except json.decoder.JSONDecodeError:
            print('Invalid substitutions_ch.json file!')
            open('substitutions_ch.json', 'w').close()


async def print_menu(channels, user, date):
    if date == datetime.date.today():
        if datetime.datetime.now().time() > datetime.time(14, 00):
            motd = 'Today\'s lunch was:'
        else:
            motd = 'Here\'s today\'s lunch:'
    elif date == datetime.date.today() + datetime.timedelta(days = 1):
        motd = 'Tomorrow\'s lunch will be (hopefully):'
    elif date < datetime.date.today():
        motd = 'The lunch on ' + date.isoformat() + ' was:'
    else:
        motd = 'The lunch on ' + date.isoformat() + ' will be:'
    for channel in channels:
        await client.send_typing(channel)
    menu_xml = urllib.request.urlopen('https://naplo.karinthy.hu/app/interface.php?view=v_canteen_export&day=' + date.isoformat()).read().decode('utf-8')
    root = ET.fromstring(menu_xml)
    lunch = root[2].text
    if lunch == None:
        if user != None:
            embed = discord.Embed(title='Error!', type='rich', color=discord.Color.red(), description='The lunch for ' + date.isoformat() + ' isn\'t available yet/anymore, or the lunch isn\'t available for the specified date.')
            await client.send_message(channels[0], user.mention, embed=embed)
    else:
        lunch = lunch.split('\n\n')
        a_menu = lunch[0].split('\n')
        b_menu = lunch[1].split('\n')
        a_menu.pop(0)
        b_menu.pop(0)
        soup = []
        while True:
            if a_menu[0] == b_menu[0]:
                soup.append(a_menu.pop(0))
                b_menu.pop(0)
            else:
                break
        a_menu = '\n'.join(a_menu)
        b_menu = '\n'.join(b_menu)
        soup = '\n'.join(soup)
        embed = discord.Embed(title=motd, type='rich', color=discord.Color.blue()).add_field(name='Leves:', value=soup).add_field(name='A menü:', value=a_menu).add_field(name='B menü:', value=b_menu).set_footer(text='Have fun!')
        if user == None:
            for channel in channels:
                await client.send_message(channel, embed=embed)
        else:
            print(channels, user.mention, embed.to_dict())
            await client.send_message(channels[0], user.mention, embed=embed)


async def print_substitutions(channel_ids, user, date):
    if date == datetime.date.today():
        if datetime.datetime.now().time() > datetime.time(16, 00):
            motd = 'Today\'s substitutions for class {} were:'
        else:
            motd = 'Here are today\'s substitutions for class {}:'
    elif date == datetime.date.today() + datetime.timedelta(days = 1):
        motd = 'Substitutions tomorrow for class {} will be:'
    elif date < datetime.date.today():
        motd = 'Substitutions on for class {} ' + date.isoformat() + ' were:'
    else:
        motd = 'Substitutions for class {} on ' + date.isoformat() + ' will be:'
    for channel_id in channel_ids:
        await client.send_typing(client.get_channel(channel_id))
    substitutions_json = urllib.request.urlopen('https://apps.karinthy.hu/helyettesites/json.php?day=' + date.isoformat()).read().decode('utf-8')
    substitutions_list = json.loads(substitutions_json)[0]['entries']
    substitutions_for_classes = { channel_id:filter(lambda entry: entry['class'] == substitutions_ch[CLASSINFO][channel_id], substitutions_list) for cannel_id in channel_ids }
    for channel_id in channel_ids:
        pass


async def daily_lunch():
    now = datetime.datetime.now()
    index = 0
    if lunch_ch[-1][TIME] >= now.time():
        for index in range(len(lunch_ch) - 1):
            if lunch_ch[index][TIME] > datetime.time: break
    while True:
        diff = datetime.datetime.combine(now.date(), lunch_ch[index][TIME]) - now
        await asyncio.sleep(diff.seconds)
        now = datetime.datetime.now()
        if abs(datetime.datetime.combine(now.date(), lunch_ch[index][TIME]) - now) > datetime.timedelta(seconds=5): continue
        if now.time() > datetime.time(14, 00):
            await print_menu(lunch_ch[index][CHANNELS], None, datetime.date.today() + datetime.timedelta(days=1))
        else:
            await print_menu(lunch_ch[index][CHANNELS], None, datetime.date.today())
        index = (index + 1) % len(lunch_ch)
        await asyncio.sleep(10)
        now = datetime.datetime.now()


@client.event
async def on_ready():
    global daily_lunch_task
    load_list('lunch')
    if len(lunch_ch) > 0:
        daily_lunch_task = client.loop.create_task(daily_lunch())
    load_list('subs')
    print('Ready!')


@client.event
async def on_message(message):
    if message.content.startswith('#'):
        await client.delete_message(message)
        channel = message.channel
        author = message.author
        command = message.content.split(' ')
        if command[0] == '#lunch':
            global daily_lunch_task
            if len(command) == 1:
                embed = discord.Embed(title='Available commands for $lunch:', type='rich', description='on HH:MM or HH\noff HH:MM or HH\ntoday\ntomorrow\nday YYYY-MM-DD or MM-DD or DD\ninfo', color=discord.Color.blue())
                await client.send_message(channel, author.mention, embed=embed)
            elif command[1] == 'on':
                if len(command) < 3:
                    embed = discord.Embed(title='Error!', description='Please type in a time for the lunch notifications!', type='rich', color=discord.Color.red())
                    await client.send_message(channel, author.mention, embed=embed)
                else:
                    try:
                        hour = int(command[2].split(':')[0])
                        if len(command[2].split(':')) == 2:
                            minute = int(command[2].split(':')[1])
                        else: minute = 0
                    except ValueError:
                        embed = discord.Embed(title='Error!', description='Please type in a valid time', type='rich', color=discord.Color.red())
                        await client.send_message(channel, author.mention, embed=embed)
                        return
                    time = datetime.time(hour, minute)
                    if len(lunch_ch) == 0:
                        lunch_ch.append({TIME:time, CHANNELS:[channel]})
                    else:
                        for i_time in range(len(lunch_ch)):
                            if lunch_ch[i_time][TIME] == time:
                                if not channel in lunch_ch[i_time][CHANNELS]:
                                    lunch_ch[i_tme][CHANNELS].append(cahnnel)
                                break
                            if lunch_ch[i_time][TIME] > time:
                                lunch_ch.insert(i_time, {TIME:time, CHANNELS:[channel]})
                                break
                            if i_time == len(lunch_ch) - 1:
                                lunch_ch.append({TIME:time, CHANNELS:[channel]})
                                break
                    save_list('lunch')
                    if daily_lunch_task != None:
                        daily_lunch_task.cancel()
                    daily_lunch_task = client.loop.create_task(daily_lunch())
                    embed = discord.Embed(title='Success!', description='You have enabled lunch notifications for this channel! You will get them every day at ' + time.strftime('%H:%M'), type='rich', color=discord.Color.green())
                    await client.send_message(channel, author.mention, embed=embed)

            elif command[1] == 'off':
                if len(command) < 3:
                    embed = discord.Embed(title='Error!', description='Please type in a time to remove!', type='rich', color=discord.Color.red())
                    await client.send_message(channel, author.mention, embed=embed)
                else:
                    try:
                        hour = int(command[2].split(':')[0])
                        if len(command[2].split(':')) == 2:
                            minute = int(command[2].split(':')[1])
                        else: minute = 0
                    except ValueError:
                        embed = discord.Embed(title='Error!', description='Please type in a valid time', type='rich', color=discord.Color.red())
                        await client.send_message(channel, author.mention, embed=embed)
                        return
                    time = datetime.time(hour, minute)
                    for i_time in range(len(lunch_ch)):
                        if lunch_ch[i_time][TIME] == time:
                            if channel in lunch_ch[i_time][CHANNELS]:
                                lunch_ch[i_time][CHANNELS].remove(channel)
                                if len(lunch_ch[i_time][CHANNELS]) == 0:
                                    lunch_ch.pop(i_time)
                                daily_lunch_task.cancel()
                                if len(lunch_ch) > 0:
                                    daily_lunch_task = client.loop.create_task(daily_lunch())
                                embed = discord.Embed(title='Success!', description='You have turned off lunch notifications for this channel at ' + time.strftime('%H:%M') + '!', type='rich', color=discord.Color.green())
                                await client.send_message(channel, author.mention, embed=embed)
                            else:
                                embed = discord.Embed(title='Error!', description='There wasn\'t a lunch notification scheduled at ' + time.strftime('%H:%M') + ' in this channel!\nTry $lunch info.', type='rich', color=discord.Color.red())
                                await client.send_message(channel, author.mention, embed=embed)
                            return
                    save_list('lunch')
                    embed = discord.Embed(title='Error!', description='There wasn\'t a lunch notification scheduled at ' + time.strftime('%H:%M') + ' in this channel!\nTry $lunch info.', type='rich', color=discord.Color.red())
                    await client.send_message(channel, author.mention, embed=embed)
            elif command[1] == 'info':
                times = []
                for i_time in range(len(lunch_ch)):
                    if channel in lunch_ch[i_time][CHANNELS]:
                        times.append(lunch_ch[i_time][TIME].strftime('%H:%M'))
                #times = '\n'.join(times)
                if len(times) == 0:
                    description = 'There aren\'t any lunch notifications set for this channel.'
                elif len(times) == 1:
                    description = 'You will get lunch notifications at ' + times[0]
                else:
                    description = 'You will get lunch notifications at the following times:\n' + '\n'.join(times)
                embed = discord.Embed(title='Here you go:', description=description, type='rich', color=discord.Color.blue())
                await client.send_message(channel, author.mention, embed=embed)
            elif command[1] == 'today':
                await print_menu([channel], author, datetime.date.today())
            elif command[1] == 'tomorrow':
                await print_menu([channel], author, datetime.date.today() + datetime.timedelta(days=1))
            elif command[1] == 'day':
                if len(command) != 3:
                    embed = discord.Embed(title='Error!', description='Please type in a date for your lunch request!', type='rich', color=discord.Color.red())
                    await client.send_message(channel, author.mention, embed=embed)
                else:
                    try:
                        date = command[2].split('-')
                        day = int(date[len(date) - 1])
                        if len(date) >= 2:
                            month = int(date[len(date) - 2])
                        else: month = datetime.date.today().month
                        if len(date) == 3:
                            year = int(date[0])
                        else: year = datetime.date.today().year
                    except ValueError:
                        embed = discord.Embed(title='Error!', description='Please type in a valid date!', type='rich', color=discord.Color.red())
                        await client.send_message(channel, author.mention, embed=embed)
                        return
                    await print_menu([channel], author, datetime.date(year, month, day))
        elif command[0] == '#subs' and False:
            if len(command) == 1:
                embed = discord.Embed(title='Available commands for $subs:', type='rich', description='on morning or evening\noff morning or evening\ntoday\ntomorrow\nnext\nday YYYY-MM-DD or MM-DD or DD\ninfo', color=discord.Color.blue())
                await client.send_message(channel, author.mention, embed=embed)
            elif command[1] == 'on':
                if len(command) == 2 or not command[2] in [MORNING, EVENING]:
                    if channel.id in substitutions_ch[CLASSINFO]:
                        embed = discord.Embed(title='Error!', description='Please enter morning or evening.', type='rich', color=discord.Color.red())
                        await client.send_message(channel, author.mention, embed=embed)
                    else:
                        embed = discord.Embed(title='Error!', description='Please enter morning or evening and a classID.', type='rich', color=discord.Color.red())
                        await client.send_message(channel, author.mention, embed=embed)
                elif len(command) == 3 and not channel.id in substitutions_ch[CLASSINFO]: 
                    embed = discord.Embed(title='Error!', description='Please enter a classID.', type='rich', color=discord.Color.red())
                    await client.send_message(channel, author.mention, embed=embed)
                elif channel in substitutions_ch[command[2]]:
                    embed = discord.Embed(title='Error!', description='Substitution notifications are already turned on in the ' + command[2] + ' for this channel.', type='rich', color=discord.Color.red())
                    await client.send_message(channel, author.mention, embed=embed)
                else:
                    pass

print('Starting...')

try:
    client.loop.run_until_complete(client.start('NDIyNDQ5ODQ2NTExODYxNzcw.DYb9UQ.nCazmnrwAkBnN-SlT77kiMGYeSs'))
except KeyboardInterrupt:
    client.loop.run_until_complete(client.logout())
    # cancel all tasks lingering
finally:
    client.loop.close()
    print('Finished.')


'test'
