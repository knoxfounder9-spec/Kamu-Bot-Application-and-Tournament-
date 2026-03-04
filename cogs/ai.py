import discord
from discord import app_commands
from discord.ext import commands
from google import genai
from google.genai import types
import os
import json
import logging
import asyncio
import aiohttp
import g4f
from duckduckgo_search import DDGS

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

def perform_web_search(query, max_results=3):
    """Performs a DuckDuckGo search and returns formatted results."""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
            if not results:
                return None
            
            formatted_results = "Web Search Results:\n"
            for i, res in enumerate(results, 1):
                formatted_results += f"{i}. {res['title']}: {res['body']} (Source: {res['href']})\n"
            return formatted_results
    except Exception as e:
        logger.warning(f"Web search failed: {e}")
        return None

class AICog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.client = None
        if GEMINI_API_KEY:
            try:
                self.client = genai.Client(api_key=GEMINI_API_KEY)
                logger.info("Gemini AI Client initialized successfully.")
            except Exception as e:
                logger.error(f"Failed to initialize Gemini Client: {e}")
        else:
            logger.warning("GEMINI_API_KEY not found. Using g4f (free/keyless) fallback. This may be slower or less reliable.")

    async def generate_response(self, channel_id, prompt, user_name):
        config = get_channel_config(channel_id)
        persona = config.get("persona", "helpful assistant")
        history_data = config.get("history", [])
        
        # --- Web Search Integration ---
        # Only search if prompt seems like a question or info request to save time
        search_context = None
        if any(keyword in prompt.lower() for keyword in ["who", "what", "where", "when", "how", "why", "search", "news", "latest"]):
            search_context = await asyncio.to_thread(perform_web_search, prompt)
        
        final_prompt = prompt
        if search_context:
            final_prompt = f"{search_context}\n\nUser Query: {prompt}\n(Use the search results above to answer if relevant, otherwise answer normally.)"

        # System Instruction for intelligence and safety
        sys_instruct = (
            f"You are an advanced AI with the persona: {persona}. You are talking to {user_name}. "
            "Be highly intelligent, helpful, and engaging. "
            "CRITICAL: Never use '@everyone' or '@here' in your responses. "
            "If you need to mention a user, use their name without the @ symbol if possible."
        )

        # --- GEMINI (Preferred) ---
        if self.client:
            try:
                contents = []
                for h in history_data:
                    role = h["role"]
                    parts = h["parts"]
                    contents.append(types.Content(role=role, parts=[types.Part.from_text(text=p) for p in parts]))

                chat = self.client.chats.create(
                    model='gemini-2.0-flash',
                    config=types.GenerateContentConfig(
                        system_instruction=sys_instruct,
                        temperature=0.7
                    ),
                    history=contents
                )
                
                response = await asyncio.to_thread(chat.send_message, final_prompt)
                text = response.text
                
                # Sanitize mentions
                text = text.replace("@everyone", "everyone").replace("@here", "here")
                
                add_history(channel_id, "user", prompt)
                add_history(channel_id, "model", text)
                return text
            except Exception as e:
                logger.error(f"Gemini Error: {e}")
                return f"Gemini Error: {e}"

        # --- Free AI Backend (Multi-Provider Fallback) ---
        else:
            # Prepare messages with history for memory
            messages = [{"role": "system", "content": sys_instruct}]
            for h in history_data:
                role = "user" if h["role"] == "user" else "assistant"
                content = " ".join(h["parts"])
                messages.append({"role": role, "content": content})
            messages.append({"role": "user", "content": final_prompt})

            # 1. Try Pollinations with different models
            pollinations_models = ["openai", "mistral", "llama"]
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
                            timeout=8
                        ) as resp:
                            if resp.status == 200:
                                text = await resp.text()
                                if text and len(text.strip()) > 0:
                                    text = text.replace("@everyone", "everyone").replace("@here", "here")
                                    if len(text) > 2000: text = text[:1997] + "..."
                                    add_history(channel_id, "user", prompt)
                                    add_history(channel_id, "model", text)
                                    return text
                except Exception:
                    continue

            # 2. Try G4F with a variety of models (Heavy & Lightweight)
            g4f_models = [
                "gpt-4o", "gpt-4", "claude-3-opus", "claude-3-sonnet", 
                "gemini-pro", "llama-3-70b", "mixtral-8x7b", "gpt-3.5-turbo"
            ]
            
            for g_model in g4f_models:
                try:
                    response = await asyncio.to_thread(
                        g4f.ChatCompletion.create,
                        model=g_model, 
                        messages=messages
                    )
                    text = str(response)
                    if text and len(text.strip()) > 5: # Minimal length check
                        text = text.replace("@everyone", "everyone").replace("@here", "here")
                        if len(text) > 2000: text = text[:1997] + "..."
                        add_history(channel_id, "user", prompt)
                        add_history(channel_id, "model", text)
                        return text
                except Exception:
                    continue

            # If all failed, return None instead of an error message
            logger.error(f"All AI providers failed for channel {channel_id}")
            return None

    # --- Commands ---

    @commands.command(name="ai")
    async def ai_chat(self, ctx, *, prompt: str):
        """Chat with the AI"""
        # Check if AI is enabled in this channel
        config = get_channel_config(ctx.channel.id)
        if not config.get("enabled"):
            return

        async with ctx.typing():
            response = await self.generate_response(ctx.channel.id, prompt, ctx.author.display_name)
            if response:
                # Use allowed_mentions to strictly prevent @everyone and @here pings
                allowed = discord.AllowedMentions(everyone=False, roles=False, users=True)
                await ctx.reply(response, allowed_mentions=allowed)
            # If response is None, we just don't reply (silent failure as requested)

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
    @app_commands.describe(persona="The personality type for the AI")
    @app_commands.choices(persona=[
        app_commands.Choice(name="Default (Helpful Assistant)", value="helpful assistant"),
        app_commands.Choice(name="Kind & Caring", value="kind and caring"),
        app_commands.Choice(name="Toxic & Rude", value="toxic and rude"),
        app_commands.Choice(name="Smart & Concise", value="smart and concise"),
        app_commands.Choice(name="Chill & Casual", value="chill and casual"),
        app_commands.Choice(name="Pirate", value="pirate"),
    ])
    async def ai_behaviour(self, interaction: discord.Interaction, persona: app_commands.Choice[str]):
        update_channel_config(interaction.channel_id, "persona", persona.value)
        # Clear history to reset context with new persona
        update_channel_config(interaction.channel_id, "history", [])
        await interaction.response.send_message(f"AI behaviour set to: **{persona.name}**. Conversation history cleared.", ephemeral=True)

    # --- Listeners ---

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        # Check if AI is enabled in this channel
        config = get_channel_config(message.channel.id)
        if not config.get("enabled"):
            return

        # Check for trigger: Reply to bot
        # Note: !ai is now handled by the command above
        is_reply = False
        if message.reference and message.reference.resolved:
            if message.reference.resolved.author.id == self.bot.user.id:
                is_reply = True

        if is_reply:
            prompt = message.content
            async with message.channel.typing():
                response = await self.generate_response(message.channel.id, prompt, message.author.display_name)
                if response:
                    # Use allowed_mentions to strictly prevent @everyone and @here pings
                    allowed = discord.AllowedMentions(everyone=False, roles=False, users=True)
                    await message.reply(response, allowed_mentions=allowed)

async def setup(bot):
    await bot.add_cog(AICog(bot))
