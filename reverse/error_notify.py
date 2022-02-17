from discordwebhook import Discord
import json
import datetime

pathContent = "content.json"
with open(pathContent) as f:
  content = json.load(f)
discord = Discord(url=content["discordErrNotifyURL"])

msg = str(datetime.datetime.now()) + ": Program is abnormal termination!"
discord.post(content=msg)
