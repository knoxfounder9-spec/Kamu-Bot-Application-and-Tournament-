import discord
from discord import app_commands
from discord.ext import commands
import google.generativeai as genai
import os
import json
import logging
import asyncio

# Configure logging
logger = logging.getLogger('discord')

# --- Constants ---
AI_CONFIG_FILE = 'ai_config.json'
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# --- Helper Functions ---
def load_ai_config():
    if not os.path.exists(AI_CONFIG_FILE):
        return {}
    with open(AI_CONFIG_FILE, 'r') as f:
        return json.load(f)

def save_ai_config(config_data):
    with open(AI_CONFIG_FILE, 'w') as f:
        json.dump(config_data, f, indent=4)

def get_channel_config(channel_id):
    config = load_ai_config()
    return config.get(str(channel_id), {
        "enabled": False,
        "voice_mode": False,
        "persona": "helpful assistant",
        "history": []
    })

def update_channel_config(channel_id, key, value):
    config = load_ai_config()
    str_id = str(channel_id)
    if str_id not in config:
        config[str_id] = {
            "enabled": False,
            "voice_mode": False,
            "persona": "helpful assistant",
            "history": []
        }
    config[str_id][key] = value
    save_ai_config(config)

def add_history(channel_id, role, message):
    config = load_ai_config()
    str_id = str(channel_id)
    if str_id not in config:
        return # Should be initialized
    
    history = config[str_id].get("history", [])
    history.append({"role": role, "parts": [message]})
    
    # Keep history manageable (last 20 turns)
    if len(history) > 40:
        history = history[-40:]
    
    config[str_id]["history"] = history
    save_ai_config(config)

class AICog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        if GEMINI_API_KEY:
            genai.configure(api_key=GEMINI_API_KEY)
        else:
            logger.warning("GEMINI_API_KEY not found. AI features will be disabled.")

    async def generate_response(self, channel_id, prompt, user_name):
        if not GEMINI_API_KEY:
            return "AI is not configured (missing API key)."

        config = get_channel_config(channel_id)
        persona = config.get("persona", "helpful assistant")
        history_data = config.get("history", [])
        
        # Create model with system instruction
        # We create a new instance to apply the specific persona for this channel
        model = genai.GenerativeModel(
            'gemini-1.5-flash',
            system_instruction=f"You are a {persona}. You are talking to {user_name}."
        )

        formatted_history = []
        for h in history_data:
            formatted_history.append({
                "role": h["role"],
                "parts": h["parts"]
            })

        # Gemini requires history to start with 'user' role
        if formatted_history and formatted_history[0]['role'] == 'model':
            formatted_history.pop(0)

        chat = model.start_chat(history=formatted_history)
        
        try:
            # Run blocking call in thread
            response = await asyncio.to_thread(chat.send_message, prompt)
            text = response.text
            
            # Update history
            # We store just the prompt, not the full system injection, since system instruction is handled by the model config now.
            add_history(channel_id, "user", prompt)
            add_history(channel_id, "model", text)
            
            return text
        except Exception as e:
            logger.error(f"AI Generation Error: {e}")
            return "I'm having trouble thinking right now."

    # --- Commands ---

    @app_commands.command(name="aion", description="Enable AI in this channel")
    @app_commands.checks.has_permissions(administrator=True)
    async def aion(self, interaction: discord.Interaction):
        update_channel_config(interaction.channel_id, "enabled", True)
        await interaction.response.send_message("AI enabled in this channel.", ephemeral=True)

    @app_commands.command(name="aioff", description="Disable AI in this channel")
    @app_commands.checks.has_permissions(administrator=True)
    async def aioff(self, interaction: discord.Interaction):
        update_channel_config(interaction.channel_id, "enabled", False)
        await interaction.response.send_message("AI disabled in this channel.", ephemeral=True)

    @app_commands.command(name="aivoicechat", description="Toggle AI voice chat mode")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.choices(mode=[
        app_commands.Choice(name="On", value="on"),
        app_commands.Choice(name="Off", value="off")
    ])
    async def aivoicechat(self, interaction: discord.Interaction, mode: app_commands.Choice[str]):
        is_on = mode.value == "on"
        update_channel_config(interaction.channel_id, "voice_mode", is_on)
        
        if is_on:
            await interaction.response.send_message("AI Voice Chat mode enabled. (Note: Actual voice synthesis requires additional setup, currently text-only response simulating voice).", ephemeral=True)
        else:
            await interaction.response.send_message("AI Voice Chat mode disabled.", ephemeral=True)

    @app_commands.command(name="ai_behaviour", description="Set the AI's personality")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(type="The personality type (e.g., kind, smart, toxic, chill)")
    async def ai_behaviour(self, interaction: discord.Interaction, type: str):
        update_channel_config(interaction.channel_id, "persona", type)
        # Clear history to reset context with new persona
        update_channel_config(interaction.channel_id, "history", [])
        await interaction.response.send_message(f"AI behaviour set to: **{type}**. Conversation history cleared.", ephemeral=True)

    # --- Listeners ---

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        # Check if AI is enabled in this channel
        config = get_channel_config(message.channel.id)
        if not config.get("enabled"):
            return

        # Check for trigger: !ai prefix OR reply to bot
        is_reply = False
        if message.reference and message.reference.resolved:
            if message.reference.resolved.author.id == self.bot.user.id:
                is_reply = True

        if message.content.startswith('!ai ') or is_reply:
            prompt = message.content
            if message.content.startswith('!ai '):
                prompt = message.content[4:]
            
            async with message.channel.typing():
                response = await self.generate_response(message.channel.id, prompt, message.author.display_name)
                await message.reply(response)

async def setup(bot):
    await bot.add_cog(AICog(bot))
