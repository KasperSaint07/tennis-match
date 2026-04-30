from app.bot.main import bot, dp
from app.bot.handlers import start, games, join, wallet, create

print(f"Bot: {bot}")
print(f"Dispatcher: {dp}")
print(f"Routers: {dp.sub_routers}")
