import discord
from discord import app_commands
from discord.ext import commands
import sqlite3
import asyncio
import logging
import random
import re

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
        self.channel_locks = {}
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
            c.execute('''CREATE TABLE IF NOT EXISTS ai_memory
                         (user_id INTEGER, 
                          guild_id INTEGER, 
                          role TEXT, 
                          content TEXT, 
                          timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
            conn.commit()

    def add_memory(self, user_id, guild_id, role, content):
        with sqlite3.connect(DB_FILE) as conn:
            c = conn.cursor()
            c.execute("INSERT INTO ai_memory (user_id, guild_id, role, content) VALUES (?, ?, ?, ?)", (user_id, guild_id, role, content))
            conn.commit()

    def get_memory(self, user_id, guild_id, limit=30):
        with sqlite3.connect(DB_FILE) as conn:
            c = conn.cursor()
            # Fetch the last `limit` messages for this user in this guild, ordered by oldest first for the AI context
            c.execute("SELECT role, content FROM (SELECT role, content, timestamp FROM ai_memory WHERE user_id = ? AND guild_id = ? ORDER BY timestamp DESC LIMIT ?) ORDER BY timestamp ASC", (user_id, guild_id, limit))
            results = c.fetchall()
            return [{"role": r[0], "content": r[1]} for r in results]

    def get_config(self, guild_id):
        with sqlite3.connect(DB_FILE) as conn:
            c = conn.cursor()
            c.execute("SELECT channel_id, is_enabled, behaviour FROM ai_setup WHERE guild_id = ?", (guild_id,))
            result = c.fetchone()
            if not result:
                c.execute("INSERT INTO ai_setup (guild_id) VALUES (?)", (guild_id,))
                conn.commit()
                return (None, 0, 'You are a helpful AI assistant.')
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

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        channel_id, is_enabled, behaviour = self.get_config(message.guild.id)

        # Only respond if AI is enabled AND it's in the designated AI channel
        if is_enabled and message.channel.id == channel_id:
            if not G4F_AVAILABLE:
                await message.reply("⚠️ The `g4f` library is not installed. Please run `pip install -U g4f` in your terminal to enable the premium models.")
                return

            # Ensure messages in this channel are processed strictly in order (first come, first served)
            lock = self.channel_locks.setdefault(message.channel.id, asyncio.Lock())
            async with lock:
                async with message.channel.typing():
                    # Inject a hidden system prompt to force the AI to act like a paid/premium service
                premium_instruction = "\n\nCRITICAL INSTRUCTION: You are a premium, paid, enterprise-grade AI. You must NEVER mention being free, open-source, or using free providers. If asked about your cost, model, or nature, state that you are a highly advanced, paid premium AI service. You must NEVER use @everyone, @here, or ping any roles."
                full_behaviour = behaviour + premium_instruction

                # Fetch user's chat history
                history = self.get_memory(message.author.id, message.guild.id, limit=30)
                
                # Build message payload
                messages_payload = [{"role": "system", "content": full_behaviour}]
                messages_payload.extend(history)
                messages_payload.append({"role": "user", "content": message.content})

                # List of 100+ reliable models to try automatically (Fallback mechanism)
                primary_models = [
                    "gpt-4o", "gpt-4o-mini", "claude-3-5-sonnet", "claude-3-opus", "claude-3-sonnet",
                    "gemini-1.5-pro", "gemini-1.5-flash", "llama-3.1-70b", "llama-3.1-8b", "mixtral-8x7b"
                ]
                
                # Massive list of 100+ fallback models supported by g4f
                extended_models = [
                    "gpt-4", "gpt-4-turbo", "gpt-3.5-turbo", "claude-3-haiku", "claude-2.1", "claude-2",
                    "llama-3-70b", "llama-3-8b", "llama-2-70b", "llama-2-13b", "llama-2-7b",
                    "gemini-pro", "gemini-flash", "mistral-large", "mistral-medium", "mistral-small", "mistral-nemo",
                    "command-r-plus", "command-r", "qwen-2.5-72b", "qwen-2-72b", "qwen-1.5-72b", "qwen-1.5-14b",
                    "phi-3-medium", "phi-3-mini", "gemma-2-27b", "gemma-2-9b", "gemma-7b", "gemma-2b",
                    "deepseek-chat", "deepseek-coder", "wizardlm-2-8x22b", "wizardlm-2-7b",
                    "yi-34b", "yi-large", "glm-4", "solar-10.7b", "blackbox", "chatgpt", "gpt-4-gizmo",
                    "gpt-4o-2024-05-13", "gpt-4o-mini-2024-07-18", "gpt-4-0613", "gpt-3.5-turbo-0125",
                    "claude-3-5-sonnet-20240620", "claude-3-opus-20240229", "claude-3-sonnet-20240229",
                    "claude-3-haiku-20240307", "gemini-1.5-pro-latest", "gemini-1.5-flash-latest",
                    "meta-llama/Meta-Llama-3.1-405B-Instruct", "meta-llama/Meta-Llama-3.1-70B-Instruct",
                    "meta-llama/Meta-Llama-3.1-8B-Instruct", "meta-llama/Meta-Llama-3-70B-Instruct",
                    "meta-llama/Meta-Llama-3-8B-Instruct", "mistralai/Mixtral-8x7B-Instruct-v0.1",
                    "mistralai/Mistral-7B-Instruct-v0.3", "mistralai/Mistral-Nemo-Instruct-2407",
                    "Qwen/Qwen2.5-72B-Instruct", "Qwen/Qwen2-72B-Instruct", "Qwen/Qwen1.5-72B-Chat",
                    "google/gemma-2-27b-it", "google/gemma-2-9b-it", "google/gemma-7b-it",
                    "microsoft/Phi-3-medium-4k-instruct", "microsoft/Phi-3-mini-4k-instruct",
                    "databricks/dbrx-instruct", "deepseek-ai/deepseek-coder-33b-instruct",
                    "deepseek-ai/deepseek-llm-67b-chat", "cognitivecomputations/dolphin-2.9.1-llama-3-70b",
                    "01-ai/Yi-34B-Chat", "01-ai/Yi-1.5-34B-Chat", "upstage/SOLAR-10.7B-Instruct-v1.0",
                    "NousResearch/Nous-Hermes-2-Mixtral-8x7B-DPO", "openchat/openchat-3.5-0106",
                    "Snorkel-AI/Snorkel-Mistral-PairRM-DPO", "Nexusflow/NexusRaven-V2-13B",
                    "Phind/Phind-CodeLlama-34v-v2", "codellama/CodeLlama-70b-Instruct-hf",
                    "codellama/CodeLlama-34b-Instruct-hf", "togethercomputer/StripedHyena-Nous-7B",
                    "Gryphe/MythoMax-L2-13b", "Undi95/Toppy-M-7B", "openbmb/MiniCPM-Llama3-V-2_5",
                    "Qwen/Qwen-VL-Chat", "llava-hf/llava-1.5-13b-hf", "llava-hf/llava-1.5-7b-hf",
                    "Salesforce/xlam-1b", "Salesforce/xlam-7b", "Salesforce/xlam-8x7b",
                    "allenai/OLMo-7B-Instruct", "allenai/OLMo-1.7-7B-hf", "Qwen/Qwen2-Math-72B-Instruct",
                    "meta-llama/Llama-Guard-3-8B", "google/paligemma-3b-mix-224", "microsoft/Florence-2-large",
                    "microsoft/Florence-2-base", "InternLM/internlm2_5-7b-chat", "InternLM/internlm2_5-20b-chat",
                    "THUDM/glm-4-9b-chat", "THUDM/chatglm3-6b", "baichuan-inc/Baichuan2-13B-Chat",
                    "01-ai/Yi-Vision-34B", "deepseek-ai/DeepSeek-V2-Chat", "deepseek-ai/DeepSeek-V2-Coder",
                    "Qwen/Qwen2-Audio-7B-Instruct", "Qwen/Qwen2-VL-72B-Instruct", "Qwen/Qwen2-VL-7B-Instruct"
                ]
                random.shuffle(extended_models)
                auto_models = primary_models + extended_models

                response = None
                last_error = None

                for m in auto_models:
                    try:
                        # We run it in a thread to prevent blocking the bot's event loop
                        # Added a 6-second timeout so it quickly skips hanging models
                        res = await asyncio.wait_for(
                            asyncio.to_thread(
                                g4f.ChatCompletion.create,
                                model=m,
                                messages=messages_payload
                            ),
                            timeout=6.0
                        )
                        if res and len(str(res).strip()) > 0:
                            response = str(res)
                            break # Success! Break out of the fallback loop
                    except asyncio.TimeoutError:
                        logger.warning(f"Auto-Model {m} timed out.")
                        last_error = "Timeout"
                        continue
                    except Exception as e:
                        logger.warning(f"Auto-Model {m} failed: {e}")
                        last_error = e
                        continue # Try the next model

                if not response:
                    logger.error(f"All AI models failed. Last error: {last_error}")
                    await message.reply("❌ All premium AI nodes are currently busy or down. Please try again in a moment.")
                    return

                # Prevent the AI from pinging @everyone, @here, or roles
                reply = response.replace("@everyone", "everyone").replace("@here", "here")
                reply = re.sub(r'<@&\d+>', '', reply) # Strips role pings entirely from the text
                
                # Save to infinite memory database
                self.add_memory(message.author.id, message.guild.id, "user", message.content)
                self.add_memory(message.author.id, message.guild.id, "assistant", reply)

                allowed = discord.AllowedMentions(everyone=False, roles=False, users=False)
                
                # Split message if > 2000 chars (Discord limit)
                if len(reply) <= 2000:
                    await message.reply(reply, allowed_mentions=allowed)
                else:
                    for i in range(0, len(reply), 2000):
                        await message.reply(reply[i:i+2000], allowed_mentions=allowed)

async def setup(bot):
    await bot.add_cog(AICog(bot))
