import discord
from discord.ext import commands
import os
import asyncio
from dotenv import load_dotenv
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('discord')

load_dotenv()

TOKEN = os.getenv('DISCORD_TOKEN')
GUILD_ID = os.getenv('GUILD_ID')

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
        if os.path.exists('./cogs'):
            for filename in os.listdir('./cogs'):
                if filename.endswith('.py') and not filename.startswith('__'):
                    try:
                        await self.load_extension(f'cogs.{filename[:-3]}')
                        logger.info(f'Loaded extension: cogs.{filename[:-3]}')
                    except Exception as e:
                        logger.error(f'Failed to load extension cogs.{filename[:-3]}: {e}')
        else:
            logger.warning("No cogs directory found.")
        
        # Sync commands
        
        # 1. Global Sync
        try:
            synced = await self.tree.sync()
            logger.info(f'Synced {len(synced)} command(s) globally')
        except Exception as e:
            logger.error(f'Failed to sync commands globally: {e}')

        # 2. Guild Sync (If GUILD_ID is provided)
        if GUILD_ID:
            try:
                guild = discord.Object(id=int(GUILD_ID))
                self.tree.copy_global_to(guild=guild)
                synced = await self.tree.sync(guild=guild)
                logger.info(f'Synced {len(synced)} command(s) to guild {GUILD_ID}')
            except Exception as e:
                logger.error(f'Failed to sync commands to guild: {e}')

    async def on_ready(self):
        logger.info(f'Logged in as {self.user} (ID: {self.user.id})')
        logger.info('------')

bot = KamuBot()

@bot.command()
@commands.is_owner()
async def sync(ctx):
    """Syncs slash commands manually."""
    try:
        synced = await bot.tree.sync()
        await ctx.send(f"Synced {len(synced)} commands globally.")
    except Exception as e:
        await ctx.send(f"Failed to sync: {e}")

@bot.command()
@commands.is_owner()
async def clear_global(ctx):
    """Clears global slash commands."""
    try:
        bot.tree.clear_commands(guild=None)
        await bot.tree.sync()
        await ctx.send("Cleared global commands.")
    except Exception as e:
        await ctx.send(f"Failed to clear global commands: {e}")

if __name__ == '__main__':
    if not TOKEN:
        logger.error("Error: DISCORD_TOKEN not found in .env")
    else:
        bot.run(TOKEN)
