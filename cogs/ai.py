import discord
from discord import app_commands
from discord.ext import commands
import sqlite3
import asyncio
import logging

logger = logging.getLogger('discord')

# Try to import g4f for the 300+ free models. 
try:
    import g4f
    G4F_AVAILABLE = True
except ImportError:
    G4F_AVAILABLE = False

DB_FILE = 'ai.db'

class AICog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.init_db()

    def init_db(self):
        with sqlite3.connect(DB_FILE) as conn:
            c = conn.cursor()
            c.execute('''CREATE TABLE IF NOT EXISTS ai_setup
                         (guild_id INTEGER PRIMARY KEY, 
                          channel_id INTEGER, 
                          is_enabled INTEGER DEFAULT 0, 
                          behaviour TEXT DEFAULT 'You are a helpful AI assistant.',
                          model TEXT DEFAULT 'gpt-3.5-turbo')''')
            conn.commit()

    def get_config(self, guild_id):
        with sqlite3.connect(DB_FILE) as conn:
            c = conn.cursor()
            c.execute("SELECT channel_id, is_enabled, behaviour, model FROM ai_setup WHERE guild_id = ?", (guild_id,))
            result = c.fetchone()
            if not result:
                c.execute("INSERT INTO ai_setup (guild_id) VALUES (?)", (guild_id,))
                conn.commit()
                return (None, 0, 'You are a helpful AI assistant.', 'gpt-3.5-turbo')
            return result

    def update_config(self, guild_id, field, value):
        self.get_config(guild_id) # Ensure exists
        with sqlite3.connect(DB_FILE) as conn:
            c = conn.cursor()
            c.execute(f"UPDATE ai_setup SET {field} = ? WHERE guild_id = ?", (value, guild_id))
            conn.commit()

    @app_commands.command(name="aion", description="Turn the AI on for this server")
    @app_commands.checks.has_permissions(administrator=True)
    async def aion(self, interaction: discord.Interaction):
        self.update_config(interaction.guild.id, 'is_enabled', 1)
        await interaction.response.send_message("✅ AI has been **enabled** for this server.", ephemeral=True)

    @app_commands.command(name="aioff", description="Turn the AI off for this server")
    @app_commands.checks.has_permissions(administrator=True)
    async def aioff(self, interaction: discord.Interaction):
        self.update_config(interaction.guild.id, 'is_enabled', 0)
        await interaction.response.send_message("🚫 AI has been **disabled** for this server.", ephemeral=True)

    @app_commands.command(name="aichannel", description="Set the channel where the AI will respond automatically")
    @app_commands.describe(channel="The channel for AI chat")
    @app_commands.checks.has_permissions(administrator=True)
    async def aichannel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        self.update_config(interaction.guild.id, 'channel_id', channel.id)
        await interaction.response.send_message(f"💬 AI channel set to {channel.mention}. The AI will now reply to all messages here.", ephemeral=True)

    @app_commands.command(name="aibehaviour", description="Set the AI's system prompt/behaviour")
    @app_commands.describe(behaviour="How the AI should act (e.g., 'You are a sarcastic robot')")
    @app_commands.checks.has_permissions(administrator=True)
    async def aibehaviour(self, interaction: discord.Interaction, behaviour: str):
        self.update_config(interaction.guild.id, 'behaviour', behaviour)
        await interaction.response.send_message(f"🧠 AI behaviour updated to:\n> {behaviour}", ephemeral=True)

    @app_commands.command(name="aimodel", description="Set the AI model (Choose from 300+ free models)")
    @app_commands.describe(model="The model name to use (e.g., gpt-4o, claude-3-opus, llama-3-70b)")
    @app_commands.checks.has_permissions(administrator=True)
    async def aimodel(self, interaction: discord.Interaction, model: str):
        self.update_config(interaction.guild.id, 'model', model)
        await interaction.response.send_message(f"⚙️ AI model set to: `{model}`\n*(Using lightning fast free providers)*", ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        channel_id, is_enabled, behaviour, model = self.get_config(message.guild.id)

        # Only respond if AI is enabled AND it's in the designated AI channel
        if is_enabled and message.channel.id == channel_id:
            if not G4F_AVAILABLE:
                await message.reply("⚠️ The `g4f` library is not installed. Please run `pip install -U g4f` in your terminal to enable the 300+ free models.")
                return

            async with message.channel.typing():
                try:
                    # Using g4f to get access to hundreds of free models (Lightweight + Heavy)
                    # We run it in a thread to prevent blocking the bot's event loop
                    response = await asyncio.to_thread(
                        g4f.ChatCompletion.create,
                        model=model,
                        messages=[
                            {"role": "system", "content": behaviour},
                            {"role": "user", "content": message.content}
                        ]
                    )
                    
                    reply = str(response)
                    
                    # Prevent the AI from pinging @everyone or @here
                    reply = reply.replace("@everyone", "everyone").replace("@here", "here")
                    allowed = discord.AllowedMentions(everyone=False, roles=False, users=False)
                    
                    # Split message if > 2000 chars (Discord limit)
                    if len(reply) <= 2000:
                        await message.reply(reply, allowed_mentions=allowed)
                    else:
                        for i in range(0, len(reply), 2000):
                            await message.reply(reply[i:i+2000], allowed_mentions=allowed)
                            
                except Exception as e:
                    logger.error(f"AI Error: {e}")
                    await message.reply(f"❌ AI Error: `{e}`\n*Tip: Try changing the model using `/aimodel` if this specific model provider is currently down.*")

async def setup(bot):
    await bot.add_cog(AICog(bot))
