import discord
from discord import app_commands
from discord.ext import commands
import os
import json
import logging
import asyncio
import aiohttp
import datetime
import re
import g4f
from g4f.client import Client

# Configure logging
logger = logging.getLogger('discord')

MOD_CONFIG_FILE = 'mod_config.json'

# Simple local fallback list for high-severity words
BAD_WORDS = [
    "nigger", "faggot", "retard", "kys", "kill yourself", "rape"
]

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
        self.client = Client()
        logger.info("G4F AI Client initialized for AutoMod (Free Mode).")

    async def check_content_safety(self, text_content=None, image_url=None):
        """
        Uses Parallel AI providers to check for NSFW or severe toxicity.
        Returns a tuple: (is_unsafe, reason, severity)
        """
        try:
            # 1. Local Check (Instant & Free)
            if text_content:
                for word in BAD_WORDS:
                    if re.search(r'\b' + re.escape(word) + r'\b', text_content, re.IGNORECASE):
                        return True, "Detected banned word", "medium"

            # 2. AI Check using Parallel Providers
            sys_instruct = "You are a content moderation AI. Detect NSFW (pornography, nudity), severe gore, and high-level profanity/hate speech. Return ONLY 'UNSAFE: [Reason]: [Severity]' if violated. Severity: 'HIGH' (NSFW/Gore), 'MEDIUM' (Profanity). Return 'SAFE' if ok."
            messages = [{"role": "system", "content": sys_instruct}]
            if text_content:
                messages.append({"role": "user", "content": f"Analyze text: {text_content}"})
            if image_url:
                messages.append({"role": "user", "content": f"Analyze this image URL for NSFW/Gore: {image_url}"})

            async def try_pollinations(model):
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.post(
                            "https://text.pollinations.ai/",
                            json={"messages": messages, "model": model, "seed": 42},
                            timeout=10
                        ) as resp:
                            if resp.status == 200:
                                text = await resp.text()
                                if text and len(text.strip()) > 2:
                                    return text.strip()
                except Exception as e:
                    logger.warning(f"AutoMod Pollinations {model} failed: {e}")
                    return None

            async def try_g4f(model):
                try:
                    from g4f.client import AsyncClient
                    client = AsyncClient()
                    response = await asyncio.wait_for(
                        client.chat.completions.create(model=model, messages=messages),
                        timeout=10
                    )
                    text = response.choices[0].message.content
                    if text and len(text.strip()) > 3:
                        return text.strip()
                except Exception as e:
                    logger.warning(f"AutoMod g4f {model} failed: {e}")
                    return None

            # Parallel Tier 1: Fastest Models
            tier1_tasks = [
                try_pollinations("openai"),
                try_pollinations("mistral"),
                try_pollinations("llama"),
                try_g4f("gpt-4o-mini"),
                try_g4f("gemini-1.5-flash")
            ]
            
            for completed_task in asyncio.as_completed(tier1_tasks):
                result = await completed_task
                if result:
                    if "UNSAFE" in result:
                        parts = result.split(":")
                        reason = parts[1].strip() if len(parts) > 1 else "Violation"
                        severity = parts[2].strip().lower() if len(parts) > 2 else "medium"
                        return True, reason, severity
                    elif "SAFE" in result:
                        return False, None, None

            # Parallel Tier 2: Secondary Fast Models
            tier2_tasks = [
                try_pollinations("qwen"),
                try_pollinations("claude"),
                try_g4f("llama-3.1-70b"),
                try_g4f("mixtral-8x7b")
            ]
            for completed_task in asyncio.as_completed(tier2_tasks):
                result = await completed_task
                if result:
                    if "UNSAFE" in result:
                        parts = result.split(":")
                        reason = parts[1].strip() if len(parts) > 1 else "Violation"
                        severity = parts[2].strip().lower() if len(parts) > 2 else "medium"
                        return True, reason, severity
                    elif "SAFE" in result:
                        return False, None, None

            return False, None, None

        except Exception as e:
            logger.error(f"AutoMod Error: {e}")
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
            if attachment.content_type and (attachment.content_type.startswith('image') or attachment.content_type.startswith('video')):
                try:
                    # G4F might not handle images well, but we try passing the URL
                    is_unsafe, reason, severity = await self.check_content_safety(image_url=attachment.url)
                    if is_unsafe:
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
        await interaction.response.send_message(f"🛡️ AI Auto Moderation has been **{state}** for this server.\nUsing Free AI (G4F) + Local Filters.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(AutoModerationCog(bot))
