import discord
from discord import app_commands
from discord.ext import commands
from google import genai
from google.genai import types
import os
import json
import logging
import asyncio
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
        # Perform search for every query to give "internet access"
        # Run in thread to avoid blocking
        search_context = await asyncio.to_thread(perform_web_search, prompt)
        
        final_prompt = prompt
        if search_context:
            final_prompt = f"{search_context}\n\nUser Query: {prompt}\n(Use the search results above to answer if relevant, otherwise answer normally.)"

        # --- GEMINI (Preferred) ---
        if self.client:
            try:
                contents = []
                for h in history_data:
                    role = h["role"]
                    parts = h["parts"]
                    contents.append(types.Content(role=role, parts=[types.Part.from_text(text=p) for p in parts]))

                sys_instruct = f"You are a {persona}. You are talking to {user_name}."

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
                
                add_history(channel_id, "user", prompt) # Store original prompt in history
                add_history(channel_id, "model", text)
                return text
            except Exception as e:
                logger.error(f"Gemini Error: {e}")
                # Fallthrough to g4f if Gemini fails? Or just return error?
                # Let's return error to avoid confusion if key is present but invalid.
                return f"Gemini Error: {e}"

        # --- G4F (Fallback / No Key) ---
        else:
            # List of providers to try in order
            # Safely build the list of providers based on what's available in the installed g4f version
            # We prioritize providers that usually don't require auth
            potential_providers = [
                'Blackbox', 
                'DuckDuckGo', 
                'DarkAI', 
                'DeepInfra', 
                'Binjie',
                'PollinationsAI' # Moved to end as it was failing
            ]
            providers = []
            
            for p_name in potential_providers:
                if hasattr(g4f.Provider, p_name):
                    providers.append(getattr(g4f.Provider, p_name))
                else:
                    logger.debug(f"g4f Provider {p_name} not found in this version.")
            
            # Add None for Auto mode as the final fallback
            providers.append(None)

            last_error = None

            for provider in providers:
                try:
                    provider_name = getattr(provider, "__name__", "Auto")
                    # logger.info(f"Trying g4f provider: {provider_name}")

                    # Construct messages for g4f
                    messages = [{"role": "system", "content": f"You are a {persona}. You are talking to {user_name}."}]
                    for h in history_data:
                        # g4f uses 'user' and 'assistant' usually
                        role = "user" if h["role"] == "user" else "assistant"
                        content = " ".join(h["parts"])
                        messages.append({"role": role, "content": content})
                    
                    messages.append({"role": "user", "content": final_prompt})

                    # Use g4f
                    # We pass model=None to let the provider pick its best default
                    response = await asyncio.to_thread(
                        g4f.ChatCompletion.create,
                        model=None, 
                        messages=messages,
                        provider=provider
                    )
                    
                    # g4f returns string directly usually
                    text = str(response)
                    
                    if not text or len(text.strip()) == 0:
                        raise Exception("Empty response")
                    
                    # Check for common error strings in response
                    if "error" in text.lower() and len(text) < 100:
                         logger.warning(f"g4f Provider {provider_name} returned error-like text: {text}")
                         # We might want to continue here, but sometimes it's just the AI saying "I made an error"
                         # Let's assume if it's short and has error, it might be a system error.
                         # But for now, let's accept it unless it's empty.

                    # Truncate to 2000 chars for Discord
                    if len(text) > 2000:
                        text = text[:1997] + "..."

                    add_history(channel_id, "user", prompt) # Store original prompt in history
                    add_history(channel_id, "model", text)
                    return text

                except Exception as e:
                    provider_name = getattr(provider, "__name__", "Auto")
                    logger.warning(f"g4f Provider {provider_name} failed: {e}")
                    last_error = e
                    continue # Try next provider
            
            # If all failed
            logger.error(f"All g4f providers failed. Last error: {last_error}")
            return "I'm having trouble thinking right now. (No API Key & All Fallbacks failed)"

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
            await ctx.reply(response)

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
                await message.reply(response)

async def setup(bot):
    await bot.add_cog(AICog(bot))
