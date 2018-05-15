KFG-bot

KFG-bot is a Dicord bot designed to send the menu of a school-canteen to specified channels at specified times every day.
KFG stands for Karinthy Frigyes Gimnázium, the highschool in whitch the designers learn.

The source, from which the bot gathers the information is an XML file extracted from the register of the mentioned school.
In order to replace it put your own link to the code the way it is shown below.
menu_xml = urllib.request.urlopen('#own link#&day=' + date.isoformat()).read().decode('utf-8')

Apparently the programme is under developement, there are some issues to be fixed and new features are coming.
KFG-bot is uncapable of processing data unless it is given in the same format as it is in KFG.
In order use KFG-bot in an other school you'll probably have to rewrite parts of the code. Discord token is read from a file named 'token' in the same directory as the script. Feel free to ask for help.
