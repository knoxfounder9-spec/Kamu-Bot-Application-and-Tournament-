import discord
from discord.ext import commands
import asyncio
import datetime

class DeathNoteCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.owner_id = 1313484931892117524

    @commands.command(name="deathnote", aliases=["dn"])
    async def deathnote(self, ctx, member: discord.Member, *, cause: str = "Heart Attack"):
        """Write a name in the Death Note. Only the owner can use this."""
        
        # 1. Exclusive Access Check
        if ctx.author.id != self.owner_id:
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

        # Cannot kill yourself (or maybe you can? Let's prevent it to be safe)
        if member.id == self.owner_id:
            await ctx.send("You cannot write your own name in the notebook.")
            return

        # 2. Initial Dramatic Embed
        embed = discord.Embed(
            title="📓 Death Note",
            description=f"The name **{member.display_name}** has been written in the notebook.\n\n**Cause of Death:** {cause}",
            color=discord.Color.dark_theme()
        )
        embed.set_image(url="https://media.giphy.com/media/131vnhJq22HwOI/giphy.gif") # Light writing aggressively
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
            death_embed.set_image(url="https://media.giphy.com/media/e20AWoQEoOB2/giphy.gif") # L falling out of chair or dramatic anime death
            await warning_msg.edit(content=None, embed=death_embed)
            
        except discord.Forbidden:
            await warning_msg.edit(content=f"❌ The Shinigami King prevented me from taking **{member.display_name}**'s life (I lack permissions to timeout this user).")
        except Exception as e:
            await warning_msg.edit(content=f"An error occurred: {e}")

async def setup(bot):
    await bot.add_cog(DeathNoteCog(bot))
