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


# lunch variables & constants
daily_lunch_task = None
TIME = 'time'
CHANNELS = 'channels'
lunch_schedule = [] # [{TIME:time, CHANNELS[channels]}]

"""
MORNING = 'morning'
EVENING = 'evening'
CLASSINFO = 'classinfo'
CHANNEL = 'channel'
CLASS = 'class'
substitutions_schedule = {MORNING:[], EVENING:[], CLASSINFO:{}} # {MORNING:[channels], EVENING:[channels], CLASSINFO:{channel_ids:class_ids}}
"""

def save_schedule(listname): # export current state of schedules to jsons
    if listname == 'lunch':
        lunch_file = open('lunch_schedule.json', 'w')
        lunch_schedule_dumpable = [{
            TIME:{'hour':i[TIME].hour, 'minute':i[TIME].minute},
            CHANNELS:[ channel.id for channel in i[CHANNELS] ]}
            for i in lunch_schedule]
        json.dump(lunch_schedule_dumpable, lunch_file)
        lunch_file.close()
    else:
        substitutions_file = open('substitutions_schedule.json', 'w')
        substitutions_schedule_dumpable = {
            MORNING:[ channel.id for channel in substitutions_schedule[MORNING] ],
            EVENING:[ channel.id for channel in substitutions_schedule[EVENING] ],
            CLASSINFO:substitutions_schedule[CLASSINFO] }
        json.dump(substitutions_schedule_dumpable, substitutions_file)
        substitutions_file.close()

def load_schedule(listname): # import schedules saved in jsons
    if listname == 'lunch':
        global lunch_schedule
        try:
            lunch_file = open('lunch_schedule.json', 'r')
            lunch_schedule_dumped = json.load(lunch_file)
            lunch_file.close()
            lunch_schedule = [ {
                TIME:datetime.time(i[TIME]['hour'], i[TIME]['minute']),
                CHANNELS:[ client.get_channel(channel_id) for channel_id in i[CHANNELS] ] }
                for i in lunch_schedule_dumped ]

        except FileNotFoundError:
            pass
        except json.decoder.JSONDecodeError:
            print('Invalid lunch_schedule.json file!')
            open('lunch_schedule.json', 'w').close()
    else:
        global substitutions_schedule
        try:
            substitutions_file = open('substitutions_schedule.json', 'r')
            substitutions_schedule_dumped = json.load(substitutions_file)
            substitutions_file.close()
            substitutions_schedule = {
            MORNING:[ client.get_channel(channel_id) for channel_id in substitutions_schedule_dumped[MORNING] ],
            EVENING:[ client.get_channel(channel_id) for channel_id in substitutions_schedule_dumped[EVENING] ],
            CLASSINFO:substitutions_schedule_dumped[CLASSINFO] }
        except FileNotFoundError:
            pass
        except json.decoder.JSONDecodeError:
            print('Invalid substitutions_schedule.json file!')
            open('substitutions_schedule.json', 'w').close()


async def send_msg_success(channel, user, message):
        embed = discord.Embed(title='Success!', type='rich', color=discord.Color.green(), description=message)
        await client.send_message(channel, user.mention, embed=embed)


async def send_msg_error(channel, user, message):
        embed = discord.Embed(title='Error!', type='rich', color=discord.Color.red(), description=message)
        await client.send_message(channel, user.mention, embed=embed)


def get_lunch_motd(date): # get lunch motd depending on date queried
    if date == datetime.date.today():
        if datetime.datetime.now().time() > datetime.time(14, 00):
           return 'Today\'s lunch was:'
        else:
            return 'Here\'s today\'s lunch:'
    elif date == datetime.date.today() + datetime.timedelta(days = 1):
        return 'Tomorrow\'s lunch will be (hopefully):'
    elif date < datetime.date.today():
        return 'The lunch on ' + date.isoformat() + ' was:'
    else:
        return 'The lunch on ' + date.isoformat() + ' will be:'


def format_lunch(rawlunch, date):
    try:
        lunch = rawlunch.split('\n\n')
        a_menu = lunch[0].split('\n')
        b_menu = lunch[1].split('\n')
        a_menu.pop(0)
        b_menu.pop(0)
        soup = []
        while True: # separate soup from the rest
            soup.append(a_menu.pop(0))
            b_menu.pop(0)
            if a_menu[0] != b_menu[0]:
                break
        a_menu = '\n'.join(a_menu)
        b_menu = '\n'.join(b_menu)
        soup = '\n'.join(soup)
        return (discord.Embed(title=get_lunch_motd(date), type='rich', color=discord.Color.blue())
                .add_field(name='Leves:', value=soup)
                .add_field(name='A menü:', value=a_menu)
                .add_field(name='B menü:', value=b_menu)
                .set_footer(text='Have fun!'))
    except:
        return discord.Embed(title=get_lunch_motd(date), type='rich', color=discord.Color.blue(), description=rawlunch) # if lunch formatting failed, just print it out unformatted


async def print_menu(channels, user, date): # print menu of [date] to [channels] replyig to [user]
    menu_xml = urllib.request.urlopen('https://naplo.karinthy.hu/app/interface.php?view=v_canteen_export&day=' + date.isoformat()).read().decode('utf-8') # get menu as an xml
    root = ET.fromstring(menu_xml) # parse it
    lunch = root[2].text # get the relevant part
    if lunch == None:
        if user != None: # only send error message on manual query
            await send_msg_error(channels[0], user, 'The lunch for ' + date.isoformat() + ' isn\'t available yet/anymore, or the lunch isn\'t available for the specified date.')
    else:
        lunch_embed = format_lunch(lunch, date)
        if user == None:
            for channel in channels:
                await client.send_message(channel, embed=lunch_embed)
        else:
            await client.send_message(channels[0], user.mention, embed=lunch_embed)


"""
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
    substitutions_for_classes = { channel_id:filter(lambda entry: entry['class'] == substitutions_schedule[CLASSINFO][channel_id], substitutions_list) for cannel_id in channel_ids }
    for channel_id in channel_ids:
        pass
"""


async def daily_lunch():
    now = datetime.datetime.now()
    index = 0 # find which time is next
    if lunch_schedule[-1][TIME] >= now.time(): 
        for index in range(len(lunch_schedule) - 1):
            if lunch_schedule[index][TIME] > datetime.time: break
    while True:
        diff = (datetime.datetime.combine(now.date(), lunch_schedule[index][TIME])
                - now # calculate time to wait
                - datetime.timedelta(seconds=30)) # stop sooner than the desired time
        await asyncio.sleep(diff.seconds) # wait (possibly a lot of time -> inaccurate)
        now = datetime.datetime.now()
        diff = datetime.datetime.combine(now.date(), lunch_schedule[index][TIME]) - now # recalculate the small difference
        await asyncio.sleep(diff.seconds) # wait (small amount of time -> accurate)
        now = datetime.datetime.now()
        print('printing lunch to ', lunch_schedule[index][CHANNELS])
        if now.time() > datetime.time(14, 00):
            await print_menu(lunch_schedule[index][CHANNELS], None, datetime.date.today() + datetime.timedelta(days=1))
        else:
            await print_menu(lunch_schedule[index][CHANNELS], None, datetime.date.today())
        index = (index + 1) % len(lunch_schedule)


async def lunch_help(args, channel, author): # $lunch
    embed = discord.Embed(title='Available commands for $lunch:', type='rich', description='on HH:MM or HH\noff HH:MM or HH\ntoday\ntomorrow\nday YYYY-MM-DD or MM-DD or DD\ninfo', color=discord.Color.blue())
    await client.send_message(channel, author.mention, embed=embed)


async def lunch_on(args, channel, author): # $lunch on
    global daily_lunch_task 
    if len(args) < 1:
        await send_msg_error(channel, author, 'Please type in a time for the lunch notifications!')
    else:
        time = args[0]
        try:
            hour = int(time.split(':')[0])
            if len(time.split(':')) == 2:
                minute = int(time.split(':')[1])
            else: minute = 0
            time = datetime.time(hour, minute)
        except ValueError:
            await send_msg_error(channel, author, 'Please type in a valid time')
            return
        if len(lunch_schedule) == 0:
            lunch_schedule.append({TIME:time, CHANNELS:[channel]})
        else:
            for i_time in range(len(lunch_schedule)):
                if lunch_schedule[i_time][TIME] == time:
                    if not channel in lunch_schedule[i_time][CHANNELS]:
                        lunch_schedule[i_tme][CHANNELS].append(cahnnel)
                    break
                if lunch_schedule[i_time][TIME] > time:
                    lunch_schedule.insert(i_time, {TIME:time, CHANNELS:[channel]})
                    break
                if i_time == len(lunch_schedule) - 1:
                    lunch_schedule.append({TIME:time, CHANNELS:[channel]})
                    break
        save_schedule('lunch')
        if daily_lunch_task != None:
            daily_lunch_task.cancel()
        daily_lunch_task = client.loop.create_task(daily_lunch())
        await send_msg_success(channel, author, 'You have enabled lunch notifications for this channel! You will get them every day at ' + time.strftime('%H:%M'))


async def lunch_off(args, channel, author): # $lunch off
    global daily_lunch_task 
    if len(args) < 1:
        await send_msg_error(channel, author, 'Please type in a time to remove!')
    else:
        time = args[0]
        try:
            hour = int(time.split(':')[0])
            if len(time.split(':')) == 2:
                minute = int(time.split(':')[1])
            else: minute = 0
            time = datetime.time(hour, minute)
        except ValueError:
            await send_msg_error(channel, author, 'Please type in a valid time')
            return
        for i_time in range(len(lunch_schedule)):
            if lunch_schedule[i_time][TIME] == time:
                if channel in lunch_schedule[i_time][CHANNELS]:
                    lunch_schedule[i_time][CHANNELS].remove(channel)
                    if len(lunch_schedule[i_time][CHANNELS]) == 0:
                        lunch_schedule.pop(i_time)
                    daily_lunch_task.cancel()
                    if len(lunch_schedule) > 0:
                        daily_lunch_task = client.loop.create_task(daily_lunch())
                    await send_msg_success(channel, author, 'You have turned off lunch notifications for this channel at ' + time.strftime('%H:%M') + '!')
                    save_schedule('lunch')
                    return
                else:
                    break
        await send_msg_error(channel, author, 'There wasn\'t a lunch notification scheduled at ' + time.strftime('%H:%M') + ' in this channel!\nTry $lunch info.')


async def lunch_info(args, channel, author): # $lunch info
    times = []
    for i_time in range(len(lunch_schedule)):
        if channel in lunch_schedule[i_time][CHANNELS]:
            times.append(lunch_schedule[i_time][TIME].strftime('%H:%M'))
    #times = '\n'.join(times)
    if len(times) == 0:
        description = 'There aren\'t any lunch notifications set for this channel.'
    elif len(times) == 1:
        description = 'You will get lunch notifications at ' + times[0]
    else:
        description = 'You will get lunch notifications at the following times:\n' + '\n'.join(times)
    embed = discord.Embed(title='Here you go:', description=description, type='rich', color=discord.Color.blue())
    await client.send_message(channel, author.mention, embed=embed)


async def lunch_today(args, channel, author): # $lunch today
    await print_menu([channel], author, datetime.date.today())


async def lunch_tomorrow(args, channel, author): # $lunch tomorrow
    await print_menu([channel], author, datetime.date.today() + datetime.timedelta(days=1))


async def lunch_day(args, channel, author): # $lunch day
    if len(args) != 1:
        await send_msg_error(channel, author, 'Please type in a date for your lunch request!')
    else:
        date = args[0]
        try:
            date = date.split('-')
            day = int(date[len(date) - 1])
            if len(date) >= 2:
                month = int(date[len(date) - 2])
            else: month = datetime.date.today().month
            if len(date) == 3:
                year = int(date[0])
            else: year = datetime.date.today().year
            date = datetime.date(year, month, day)
        except ValueError:
            await send_msg_error(channel, author, 'Please type in a valid date!')
            return
        await print_menu([channel], author, date)


@client.event
async def on_ready():
    global daily_lunch_task
    load_schedule('lunch')
    if len(lunch_schedule) > 0:
        daily_lunch_task = client.loop.create_task(daily_lunch())
    print('Ready!')


commands = {
    '$lunch': lunch_help,
    '$lunch on': lunch_on,
    '$lunch off': lunch_off,
    '$lunch info': lunch_info,
    '$lunch today': lunch_today,
    '$lunch tomorrow': lunch_tomorrow,
    '$lunch day': lunch_day }


@client.event
async def on_message(message):
    command = ' '.join(message.content.split(' ')[:2])
    args = message.content.split(' ')[2:]
    if message.content.startswith('$') and command in commands: # check if message is a command
        await client.delete_message(message)
        channel = message.channel
        await client.send_typing(channel)
        author = message.author
        await commands[command](args, channel, author) # run the command


"""
        elif command[0] == '$subs' and False:
            if len(command) == 1:
                embed = discord.Embed(title='Available commands for $subs:', type='rich', description='on morning or evening\noff morning or evening\ntoday\ntomorrow\nnext\nday YYYY-MM-DD or MM-DD or DD\ninfo', color=discord.Color.blue())
                await client.send_message(channel, author.mention, embed=embed)
            elif command[1] == 'on':
                if len(command) == 2 or not command[2] in [MORNING, EVENING]:
                    if channel.id in substitutions_schedule[CLASSINFO]:
                        embed = discord.Embed(title='Error!', description='Please enter morning or evening.', type='rich', color=discord.Color.red())
                        await client.send_message(channel, author.mention, embed=embed)
                    else:
                        embed = discord.Embed(title='Error!', description='Please enter morning or evening and a classID.', type='rich', color=discord.Color.red())
                        await client.send_message(channel, author.mention, embed=embed)
                elif len(command) == 3 and not channel.id in substitutions_schedule[CLASSINFO]: 
                    embed = discord.Embed(title='Error!', description='Please enter a classID.', type='rich', color=discord.Color.red())
                    await client.send_message(channel, author.mention, embed=embed)
                elif channel in substitutions_schedule[command[2]]:
                    embed = discord.Embed(title='Error!', description='Substitution notifications are already turned on in the ' + command[2] + ' for this channel.', type='rich', color=discord.Color.red())
                    await client.send_message(channel, author.mention, embed=embed)
                else:
                    pass
"""


print('Starting...')

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

