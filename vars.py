#💗BHARAT💗
# Add your details here and then deploy by clicking on HEROKU Deploy button
import os
from os import environ

API_ID = int(environ.get("API_ID", "26729193"))
API_HASH = environ.get("API_HASH", "a94598ef642481e35466292df95f251e")
BOT_TOKEN = environ.get("BOT_TOKEN", "7246658062:AAFihBmIU_oShvmhz1f-r8Rxu4dCt4Y950A")
OWNER = int(environ.get("OWNER", "1012164907"))
CREDIT = "💗 BHARAT 💗"
AUTH_USER = os.environ.get('AUTH_USERS', '1012164907').split(',')
AUTH_USERS = [int(user_id) for user_id in AUTH_USER]
if int(OWNER) not in AUTH_USERS:
    AUTH_USERS.append(int(OWNER))
  
#WEBHOOK = True  # Don't change this
#PORT = int(os.environ.get("PORT", 8080))  # Default to 8000 if not set
