import discord
from discord.ext import commands
import os
import asyncio
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv('DISCORD_TOKEN')

class KamuBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        
        super().__init__(
            command_prefix=commands.when_mentioned_or('!'),
            intents=intents,
            help_command=None
        )

    async def setup_hook(self):
        # Load cogs
        for filename in os.listdir('./src/cogs'):
            if filename.endswith('.py') and not filename.startswith('__'):
                await self.load_extension(f'src.cogs.{filename[:-3]}')
        
        # Sync commands
        try:
            synced = await self.tree.sync()
            print(f'Synced {len(synced)} command(s)')
        except Exception as e:
            print(f'Failed to sync commands: {e}')

    async def on_ready(self):
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        print('------')

bot = KamuBot()

if __name__ == '__main__':
    if not TOKEN:
        print("Error: DISCORD_TOKEN not found in .env")
    else:
        bot.run(TOKEN)
