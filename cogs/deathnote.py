import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import datetime
import sqlite3

DB_FILE = 'deathnote.db'

class DeathNoteCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.owner_ids = [1313484931892117524, 1180978822624071792]
        self.init_db()

    def init_db(self):
        with sqlite3.connect(DB_FILE) as conn:
            c = conn.cursor()
            c.execute('''CREATE TABLE IF NOT EXISTS guild_configs
                         (guild_id INTEGER PRIMARY KEY, role_id INTEGER)''')
            conn.commit()

    def get_allowed_role(self, guild_id):
        with sqlite3.connect(DB_FILE) as conn:
            c = conn.cursor()
            c.execute("SELECT role_id FROM guild_configs WHERE guild_id = ?", (guild_id,))
            result = c.fetchone()
            return result[0] if result else None

    @app_commands.command(name="deathnoteroleperm", description="Set the role allowed to use the Death Note")
    @app_commands.describe(role="The role to allow")
    @app_commands.checks.has_permissions(administrator=True)
    async def deathnote_role_perm(self, interaction: discord.Interaction, role: discord.Role):
        with sqlite3.connect(DB_FILE) as conn:
            c = conn.cursor()
            c.execute("INSERT OR REPLACE INTO guild_configs (guild_id, role_id) VALUES (?, ?)", (interaction.guild.id, role.id))
            conn.commit()
        await interaction.response.send_message(f"Death Note permission granted to {role.mention}.", ephemeral=True)

    @deathnote_role_perm.error
    async def deathnote_role_perm_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("You need Administrator permissions to use this command.", ephemeral=True)

    @commands.command(name="deathnote", aliases=["dn"])
    async def deathnote(self, ctx, member: discord.Member, *, cause: str = "Heart Attack"):
        """Write a name in the Death Note."""
        
        # 1. Exclusive Access Check
        allowed = False
        if ctx.author.id in self.owner_ids:
            allowed = True
        else:
            allowed_role_id = self.get_allowed_role(ctx.guild.id)
            if allowed_role_id and any(role.id == allowed_role_id for role in ctx.author.roles):
                allowed = True

        if not allowed:
            embed = discord.Embed(
                title="📓 Access Denied",
                description="You are not the owner of this notebook...",
                color=discord.Color.dark_grey()
            )
            embed.set_image(url="https://media.giphy.com/media/YmZOBDYBcmWK4/giphy.gif") # Ryuk laughing
            await ctx.send(embed=embed)
            return

        # Cannot kill the bot
        if member.id == self.bot.user.id:
            await ctx.send("Shinigami cannot be killed.")
            return

        # Cannot kill owners
        if member.id in self.owner_ids:
            await ctx.send("You cannot write a Shinigami King's name in the notebook.")
            return

        # 2. Initial Dramatic Embed
        embed = discord.Embed(
            title="📓 Death Note",
            description=f"The name **{member.display_name}** has been written in the notebook.\n\n**Cause of Death:** {cause}",
            color=discord.Color.dark_theme()
        )
        # Replaced with a reliable Tenor GIF of Light writing aggressively
        embed.set_image(url="https://media1.tenor.com/m/7H1v0g1kY1UAAAAd/death-note-light-yagami.gif") 
        embed.set_footer(text="The human whose name is written in this note shall die in 40 seconds.")
        
        await ctx.send(embed=embed)

        # 3. The 40-Second Rule
        await asyncio.sleep(35)
        
        # 5-second warning
        warning_msg = await ctx.send(f"⏳ 5 seconds remaining for {member.mention}...")
        await asyncio.sleep(5)

        # 4. The "Death" Effect (1 Hour Timeout)
        try:
            duration = datetime.timedelta(hours=1)
            await member.timeout(duration, reason=f"Death Note: {cause}")
            
            death_embed = discord.Embed(
                title="💀 Eliminated",
                description=f"**{member.display_name}** has died of: *{cause}*.\nThey have been timed out for 1 hour.",
                color=discord.Color.dark_red()
            )
            death_embed.set_image(url="https://media.giphy.com/media/e20AWoQEoOB2/giphy.gif") # L falling out of chair
            await warning_msg.edit(content=None, embed=death_embed)
            
        except discord.Forbidden:
            await warning_msg.edit(content=f"❌ The Shinigami King prevented me from taking **{member.display_name}**'s life (I lack permissions to timeout this user).")
        except Exception as e:
            await warning_msg.edit(content=f"An error occurred: {e}")

async def setup(bot):
    await bot.add_cog(DeathNoteCog(bot))
