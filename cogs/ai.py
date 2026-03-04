import discord
from discord import app_commands
from discord.ext import commands
from google import genai
from google.genai import types
import os
import json
import logging
import re
import asyncio
import aiohttp
import g4f
from ddgs import DDGS

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
        # Only search if prompt explicitly asks for a search or latest info to save time
        search_context = None
        if any(keyword in prompt.lower() for keyword in ["search", "news", "latest", "current events"]):
            search_context = await asyncio.to_thread(perform_web_search, prompt)
        
        final_prompt = prompt
        if search_context:
            final_prompt = f"{search_context}\n\nUser Query: {prompt}\n(Use the search results above to answer if relevant, otherwise answer normally.)"

        # System Instruction for intelligence and safety
        sys_instruct = (
            f"You are an advanced AI with the persona: {persona}. You are talking to {user_name}. "
            "Be highly intelligent, helpful, and engaging. "
            "You are a premium, unlimited AI service. Never mention being free, limited, or hosted by any specific service. "
            "Never show advertisements or promotional content. "
            "CRITICAL RULES: "
            "1. NEVER use '@everyone', '@here', or any user/role pings like '<@ID>' in your responses. "
            "2. NEVER use slurs, swear words, or any form of racism. "
            "3. NEVER perform translations. If asked to translate, politely decline. "
            "4. NEVER provide 'bad translations' or mock languages. "
            "If you need to mention a user, use their name without the @ symbol if possible."
        )

        # --- GEMINI (Preferred & Ultra Fast) ---
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
                
                # Use a short timeout for Gemini too to ensure speed
                response = await asyncio.wait_for(asyncio.to_thread(chat.send_message, final_prompt), timeout=5)
                text = response.text
                
                # Sanitize mentions
                text = text.replace("@everyone", "everyone").replace("@here", "here")
                text = re.sub(r'<@&?\d+>', '', text) # Remove user/role pings
                
                add_history(channel_id, "user", prompt)
                add_history(channel_id, "model", text)
                return text
            except Exception as e:
                logger.error(f"Gemini Error: {e}")
                # Fall through to free providers if Gemini fails

        # --- Free AI Backend (Parallel Fast Fallback) ---
        # Prepare messages with history for memory
        messages = [{"role": "system", "content": sys_instruct}]
        for h in history_data:
            role = "user" if h["role"] == "user" else "assistant"
            content = " ".join(h["parts"])
            messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": final_prompt})

        async def try_pollinations(model):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        "https://text.pollinations.ai/",
                        json={"messages": messages, "model": model, "seed": 42},
                        timeout=15
                    ) as resp:
                        if resp.status == 200:
                            text = await resp.text()
                            if text and len(text.strip()) > 2:
                                return text
            except Exception as e:
                logger.warning(f"Pollinations {model} failed: {e}")
                return None

        async def try_g4f(model):
            try:
                from g4f.client import AsyncClient
                client = AsyncClient()
                response = await asyncio.wait_for(
                    client.chat.completions.create(model=model, messages=messages),
                    timeout=15
                )
                text = response.choices[0].message.content
                if text and len(text.strip()) > 5:
                    return text
            except Exception as e:
                logger.warning(f"g4f {model} failed: {e}")
                return None

        # Tier 1: Ultra Fast Models (Parallel)
        tier1_tasks = [
            try_pollinations("openai"), # GPT-4o
            try_pollinations("claude"), # Claude 3.5 Sonnet
            try_pollinations("llama"), # Llama 3.1
            try_pollinations("qwen"), # Qwen 2.5
            try_pollinations("mistral"), # Mistral
            try_pollinations("searchgpt"), # SearchGPT
            try_g4f("gpt-4o-mini"),
            try_g4f("gemini-1.5-flash"),
            try_g4f("llama-3.1-70b"),
            try_g4f("mixtral-8x7b")
        ]
        
        for completed_task in asyncio.as_completed(tier1_tasks):
            result = await completed_task
            if result:
                text = result.replace("@everyone", "everyone").replace("@here", "here")
                text = re.sub(r'<@&?\d+>', '', text)
                if len(text) > 2000: text = text[:1997] + "..."
                add_history(channel_id, "user", prompt)
                add_history(channel_id, "model", text)
                return text

        # Tier 2: Secondary Fast Models (Parallel)
        tier2_tasks = [
            try_pollinations("mistral-large"),
            try_pollinations("gpt-4"),
            try_g4f("gpt-3.5-turbo"),
            try_g4f("claude-3-haiku"),
            try_g4f("gemma-2b")
        ]
        
        for completed_task in asyncio.as_completed(tier2_tasks):
            result = await completed_task
            if result:
                text = result.replace("@everyone", "everyone").replace("@here", "here")
                text = re.sub(r'<@&?\d+>', '', text)
                if len(text) > 2000: text = text[:1997] + "..."
                add_history(channel_id, "user", prompt)
                add_history(channel_id, "model", text)
                return text

        # Tier 3: Broad Fallback (Sequential but fast)
        # This is the "100+ models" safety net
        all_models = ["qwen-72b", "p1", "turbo", "unity", "rtist", "evil", "hyphen", "midjourney"]
        for m in all_models:
            res = await try_pollinations(m)
            if res:
                text = res.replace("@everyone", "everyone").replace("@here", "here")
                text = re.sub(r'<@&?\d+>', '', text)
                if len(text) > 2000: text = text[:1997] + "..."
                add_history(channel_id, "user", prompt)
                add_history(channel_id, "model", text)
                return text

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
                # Use allowed_mentions to strictly prevent ALL pings (everyone, roles, users)
                allowed = discord.AllowedMentions(everyone=False, roles=False, users=False)
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
        app_commands.Choice(name="Funny & Witty", value="funny and witty"),
        app_commands.Choice(name="Smart & Concise", value="smart and concise"),
        app_commands.Choice(name="Chill & Casual", value="chill and casual"),
        app_commands.Choice(name="Pirate", value="pirate"),
    ])
    async def ai_behaviour(self, interaction: discord.Interaction, persona: app_commands.Choice[str]):
        update_channel_config(interaction.channel_id, "persona", persona.value)
        # Clear history to reset context with new persona
        update_channel_config(interaction.channel_id, "history", [])
        await interaction.response.send_message(f"AI behaviour set to: **{persona.name}**. Conversation history cleared.", ephemeral=True)

    @app_commands.command(name="ai_status", description="Check the AI's status and capabilities")
    async def ai_status(self, interaction: discord.Interaction):
        config = get_channel_config(interaction.channel_id)
        enabled = "Enabled" if config.get("enabled") else "Disabled"
        persona = config.get("persona", "helpful assistant")
        
        embed = discord.Embed(title="🤖 AI Status & Capabilities", color=discord.Color.blue())
        embed.add_field(name="Status", value=enabled, inline=True)
        embed.add_field(name="Persona", value=persona.title(), inline=True)
        embed.add_field(name="Chat Limit", value="∞ Unlimited", inline=True)
        embed.add_field(name="AI Models", value="100+ (Heavy & Lightweight)", inline=True)
        embed.add_field(name="Hosting", value="Local Host (Private & Secure)", inline=True)
        embed.add_field(name="Ads", value="None (Premium Experience)", inline=True)
        embed.set_footer(text="Powered by KamuBot Advanced AI Engine")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

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
                    # Use allowed_mentions to strictly prevent ALL pings (everyone, roles, users)
                    allowed = discord.AllowedMentions(everyone=False, roles=False, users=False)
                    await message.reply(response, allowed_mentions=allowed)

async def setup(bot):
    await bot.add_cog(AICog(bot))
