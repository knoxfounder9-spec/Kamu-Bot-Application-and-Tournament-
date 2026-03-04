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
        Uses Pollinations.ai (Free AI) to check for NSFW or severe toxicity.
        Returns a tuple: (is_unsafe, reason, severity)
        Severity: 'high' (NSFW/Gore) or 'medium' (Swears/Toxicity)
        """
        try:
            # 1. Local Check (Fast & Free)
            if text_content:
                for word in BAD_WORDS:
                    if re.search(r'\b' + re.escape(word) + r'\b', text_content, re.IGNORECASE):
                        return True, "Detected banned word", "medium"

            # 2. AI Check using Pollinations.ai with G4F Fallback
            messages = []
            sys_instruct = "You are a content moderation AI. Detect NSFW (pornography, nudity), severe gore, and high-level profanity/hate speech. Return ONLY 'UNSAFE: [Reason]: [Severity]' if violated. Severity: 'HIGH' (NSFW/Gore), 'MEDIUM' (Profanity). Return 'SAFE' if ok."
            messages.append({"role": "system", "content": sys_instruct})

            if text_content:
                messages.append({"role": "user", "content": f"Analyze text: {text_content}"})
            if image_url:
                messages.append({"role": "user", "content": f"Analyze this image URL for NSFW/Gore: {image_url}"})

            result = None
            
            # 1. Try Pollinations with different models (Expanded list)
            pollinations_models = [
                "openai", "mistral", "llama", "searchgpt", "qwen", "qwen-72b",
                "claude", "gpt-4", "p1", "midjourney", "flux", "turbo", "unity", 
                "rtist", "evil", "hyphen", "minimal", "creative", "surreal", 
                "cyberpunk", "anime", "fantasy", "cinematic", "photography"
            ]
            for model_name in pollinations_models:
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.post(
                            "https://text.pollinations.ai/",
                            json={
                                "messages": messages,
                                "model": model_name,
                                "seed": 42
                            },
                            timeout=10
                        ) as resp:
                            if resp.status == 200:
                                text = await resp.text()
                                if text and len(text.strip()) > 2:
                                    result = text.strip()
                                    break
                except Exception:
                    continue

            # 2. G4F Fallback with multiple models
            if not result:
                g4f_models = [
                    # OpenAI
                    "gpt-4o", "gpt-4o-mini", "gpt-4", "gpt-4-turbo", "gpt-4-0613", "gpt-4-32k",
                    "gpt-4-0125-preview", "gpt-4-1106-preview", "gpt-4-vision-preview",
                    "gpt-3.5-turbo", "gpt-3.5-turbo-16k", "gpt-3.5-turbo-0125", "gpt-3.5-turbo-1106",
                    # Anthropic
                    "claude-3-5-sonnet", "claude-3-opus", "claude-3-sonnet", "claude-3-haiku", 
                    "claude-3-5-haiku", "claude-2.1", "claude-2", "claude-instant-1.2",
                    # Google
                    "gemini-pro", "gemini-flash", "gemini-1.5-pro", "gemini-1.5-flash", 
                    "gemini-1.5-flash-8b", "gemini-1.0-pro", "gemini-pro-vision",
                    # Meta
                    "llama-3-70b", "llama-3-8b", "llama-2-70b", "llama-2-13b", "codellama-34b", "codellama-70b",
                    "llama-3.1-405b", "llama-3.1-70b", "llama-3.1-8b", "llama-3.2-1b", "llama-3.2-3b", 
                    "llama-3.2-11b", "llama-3.2-90b",
                    # Mistral
                    "mixtral-8x7b", "mixtral-8x22b", "mistral-7b", "mistral-medium", "mistral-large", 
                    "mistral-nemo", "mistral-tiny", "mistral-small", "open-mixtral-8x7b", "open-mixtral-8x22b",
                    # Qwen
                    "qwen-1.5-72b", "qwen-1.5-110b", "qwen-1.5-14b", "qwen-1.5-7b", "qwen-2-72b", "qwen-2-7b",
                    "qwen-2.5-72b", "qwen-2.5-7b", "qwen-2.5-1.5b",
                    # Microsoft
                    "phi-3-mini", "phi-3-medium", "phi-3-vision", "phi-3-small", "phi-3.5-mini", 
                    "phi-3.5-moe", "phi-2",
                    # DeepSeek
                    "deepseek-coder", "deepseek-chat", "deepseek-v2", "deepseek-v2.5", "deepseek-chat-v2",
                    # Others
                    "blackbox", "pi", "command-r", "command-r-plus", 
                    "gemma-7b", "gemma-2b", "gemma-2-9b", "gemma-2-27b", "gemma-2-2b",
                    "solar-10-7b", "yi-34b", "yi-1.5-34b", "yi-1.5-9b", "yi-34b-chat",
                    "dalle-3", "wizardlm-2-8x22b", "dbrx-instruct", "openchat-3.5",
                    "nous-hermes-2-mixtral-8x7b", "dolphin-2.6-mixtral-8x7b", "openchat-3.6",
                    "falcon-180b", "falcon-40b", "hermes-2-pro-llama-3-8b", "stable-diffusion-xl"
                ]
                for g_model in g4f_models:
                    try:
                        response = await asyncio.to_thread(
                            g4f.ChatCompletion.create,
                            model=g_model, 
                            messages=messages
                        )
                        text = str(response).strip()
                        if text and len(text) > 3:
                            result = text
                            break
                    except Exception:
                        continue
            
            if result and "UNSAFE" in result:
                # Parse result: UNSAFE: Reason: Severity
                parts = result.split(":")
                reason = parts[1].strip() if len(parts) > 1 else "Violation"
                severity = parts[2].strip().lower() if len(parts) > 2 else "medium"
                return True, reason, severity
                
            return False, None, None

        except Exception as e:
            logger.error(f"AutoMod Pollinations Error: {e}")
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
