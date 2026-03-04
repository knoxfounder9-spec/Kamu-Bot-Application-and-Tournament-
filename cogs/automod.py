import discord
from discord import app_commands
from discord.ext import commands
import os
import json
import logging
import aiohttp
import asyncio
import datetime
from google import genai
from google.genai import types

# Configure logging
logger = logging.getLogger('discord')

MOD_CONFIG_FILE = 'mod_config.json'
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

def load_mod_config():
    if not os.path.exists(MOD_CONFIG_FILE):
        return {}
    with open(MOD_CONFIG_FILE, 'r') as f:
        return json.load(f)

def save_mod_config(config):
    with open(MOD_CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)

class AutoModerationCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.client = None
        if GEMINI_API_KEY:
            try:
                self.client = genai.Client(api_key=GEMINI_API_KEY)
                logger.info("Gemini AI Client initialized for AutoMod.")
            except Exception as e:
                logger.error(f"Failed to initialize Gemini Client for AutoMod: {e}")
        else:
            logger.warning("GEMINI_API_KEY not found. AutoMod will be limited.")

    async def check_content_safety(self, text_content=None, image_bytes=None, mime_type=None):
        """
        Uses Gemini to check for NSFW or severe toxicity.
        Returns a tuple: (is_unsafe, reason, severity)
        Severity: 'high' (NSFW/Gore) or 'medium' (Swears/Toxicity)
        """
        if not self.client:
            return False, None, None

        try:
            contents = []
            parts = []
            
            # System Instruction
            sys_instruct = "You are a strict content moderation AI. Your job is to detect NSFW (pornography, nudity, sexually explicit content), severe gore, and high-level profanity/hate speech. Return ONLY 'UNSAFE: [Reason]: [Severity]' if the content violates these rules. Severity must be 'HIGH' for NSFW/Gore and 'MEDIUM' for Profanity/Hate Speech. Return 'SAFE' if it is acceptable. Be concise."

            if text_content:
                parts.append(types.Part.from_text(text=f"Analyze this text for severe toxicity, hate speech, or explicit sexual content: {text_content}"))
            
            if image_bytes:
                parts.append(types.Part.from_bytes(data=image_bytes, mime_type=mime_type))
                parts.append(types.Part.from_text(text="Analyze this image/gif. Is it NSFW, pornographic, or contain severe gore?"))

            if not parts:
                return False, None, None

            contents.append(types.Content(role="user", parts=parts))

            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model='gemini-2.0-flash',
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=sys_instruct,
                    temperature=0.0 # Deterministic
                )
            )
            
            result = response.text.strip()
            if result.startswith("UNSAFE"):
                # Parse result: UNSAFE: Reason: Severity
                parts = result.split(":")
                reason = parts[1].strip() if len(parts) > 1 else "Violation"
                severity = parts[2].strip().lower() if len(parts) > 2 else "medium"
                return True, reason, severity
            return False, None, None

        except Exception as e:
            logger.error(f"AutoMod AI Error: {e}")
            return False, None, None

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        # Load config to check if enabled for this guild
        if not message.guild:
            return
            
        config = load_mod_config()
        guild_id = str(message.guild.id)
        if guild_id not in config or not config[guild_id].get("enabled", False):
            return

        # Check Text
        if message.content:
            is_unsafe, reason, severity = await self.check_content_safety(text_content=message.content)
            if is_unsafe:
                await self.handle_violation(message, reason, severity)
                return

        # Check Attachments (Images/GIFs)
        for attachment in message.attachments:
            if attachment.content_type and (attachment.content_type.startswith('image') or attachment.content_type.startswith('video')): # GIFs are often video/mp4 or image/gif
                try:
                    # Limit size to avoid memory issues (e.g., 10MB)
                    if attachment.size > 10 * 1024 * 1024:
                        continue

                    async with aiohttp.ClientSession() as session:
                        async with session.get(attachment.url) as resp:
                            if resp.status == 200:
                                data = await resp.read()
                                is_unsafe, reason, severity = await self.check_content_safety(image_bytes=data, mime_type=attachment.content_type)
                                if is_unsafe:
                                    # Force HIGH severity for image violations (usually NSFW)
                                    await self.handle_violation(message, reason, "high")
                                    return
                except Exception as e:
                    logger.error(f"Failed to scan attachment: {e}")

    async def handle_violation(self, message, reason, severity):
        try:
            await message.delete()
            
            action_taken = "Message Removed"
            
            # Punishment Logic
            if severity == "high":
                # Mute for 1 Hour
                try:
                    duration = datetime.timedelta(hours=1)
                    await message.author.timeout(duration, reason=f"AutoMod: {reason}")
                    action_taken = "Message Removed + Muted (1hr)"
                except discord.Forbidden:
                    action_taken += " (Failed to Mute - Missing Permissions)"
                except Exception as e:
                    logger.error(f"Failed to timeout user: {e}")
                    action_taken += " (Failed to Mute)"

            # DM the user
            try:
                embed = discord.Embed(title="⚠️ AutoMod Violation", color=discord.Color.red())
                embed.description = f"Your content in **{message.guild.name}** was flagged."
                embed.add_field(name="Reason", value=reason)
                embed.add_field(name="Action Taken", value=action_taken)
                embed.set_footer(text="Please adhere to the server rules.")
                await message.author.send(embed=embed)
            except discord.Forbidden:
                pass # User has DMs closed
            
            # Log to channel
            temp_msg = await message.channel.send(f"⚠️ {message.author.mention}, violation detected: **{reason}**. Action: {action_taken}")
            await asyncio.sleep(10)
            try:
                await temp_msg.delete()
            except:
                pass

        except discord.NotFound:
            pass # Message already deleted

    @app_commands.command(name="automod", description="Configure AI Auto Moderation")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(status="Enable or Disable AutoMod")
    @app_commands.choices(status=[
        app_commands.Choice(name="Enable", value="Enable"),
        app_commands.Choice(name="Disable", value="Disable")
    ])
    async def automod(self, interaction: discord.Interaction, status: app_commands.Choice[str]):
        config = load_mod_config()
        guild_id = str(interaction.guild_id)
        
        if guild_id not in config:
            config[guild_id] = {}
        
        enabled = (status.value == "Enable")
        config[guild_id]["enabled"] = enabled
        save_mod_config(config)
        
        state = "ENABLED" if enabled else "DISABLED"
        await interaction.response.send_message(f"🛡️ AI Auto Moderation has been **{state}** for this server.\nIt will scan for NSFW images/GIFs (Mute 1hr) and severe profanity (Warn).", ephemeral=True)

async def setup(bot):
    await bot.add_cog(AutoModerationCog(bot))
