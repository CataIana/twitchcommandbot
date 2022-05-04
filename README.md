# twitchcommandbot
A bot for allowing twitch messages and commands to be run in a discord server

##  Setup

* Rename `exampleconfig.json` to `config.json`
* Create a discord bot, and a twitch application and fill in the necessary details
* Set your trusted users as bot owners by putting their discord IDs into the bot owners array. They will have access to the bot on every server no matter what
* If you use uptime robot, your query url and heartbeat frequency can be set
* Install the required dependencies `sudo pip3 install --upgrade -r requirements.txt`
* Run the bot with `python3 main.py`
