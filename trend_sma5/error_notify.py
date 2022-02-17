import requests
from discordwebhook import Discord
import json

pathContent = "content.json"
with open(pathContent) as f:
  content = json.load(f)
discord = Discord(url=content["discordUrl"])
discord.post(content="Program is abnormal termination!")
