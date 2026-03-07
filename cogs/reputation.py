import discord
from discord import app_commands
from discord.ext import commands
import json
import os
import math

REP_FILE = 'reputation.json'

def load_rep_stats():
    if not os.path.exists(REP_FILE):
        return {}
    with open(REP_FILE, 'r') as f:
        return json.load(f)

def save_rep_stats(stats):
    with open(REP_FILE, 'w') as f:
        json.dump(stats, f, indent=4)

class ReputationCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def update_rep(self, user_id, amount):
        stats = load_rep_stats()
        user_key = str(user_id)
        if user_key not in stats:
            stats[user_key] = {"rep": 0}
        
        stats[user_key]["rep"] += amount
        save_rep_stats(stats)
        return stats[user_key]["rep"]

    @commands.command(name="+rep")
    async def add_rep(self, ctx, user: discord.Member):
        if ctx.author.id != 1313484931892117524:
            await ctx.send("You do not have permission to use this command.")
            return

        if user.id == ctx.author.id:
            await ctx.send("You cannot give reputation to yourself!")
            return
        
        new_rep = self.update_rep(user.id, 1)
        await ctx.send(f"**+1 Reputation** given to {user.mention}! They now have **{new_rep}** rep.")

    @commands.command(name="-rep")
    async def remove_rep(self, ctx, user: discord.Member):
        if ctx.author.id != 1313484931892117524:
            await ctx.send("You do not have permission to use this command.")
            return

        if user.id == ctx.author.id:
            await ctx.send("You cannot remove reputation from yourself!")
            return
        
        new_rep = self.update_rep(user.id, -1)
        await ctx.send(f"**-1 Reputation** removed from {user.mention}. They now have **{new_rep}** rep.")

    @app_commands.command(name="repleaderboard", description="Show the Reputation Leaderboard")
    async def repleaderboard(self, interaction: discord.Interaction):
        stats = load_rep_stats()
        if not stats:
            await interaction.response.send_message("No reputation stats available yet.", ephemeral=True)
            return

        # Sort by Rep descending
        sorted_stats = sorted(stats.items(), key=lambda item: item[1]['rep'], reverse=True)
        
        items_per_page = 8
        pages = math.ceil(len(sorted_stats) / items_per_page)
        
        def create_embed(page):
            start = page * items_per_page
            end = start + items_per_page
            current_page_data = sorted_stats[start:end]
            
            embed = discord.Embed(title="🌟 Reputation Leaderboard 🌟", color=discord.Color.purple())
            description = ""
            for i, (user_id, data) in enumerate(current_page_data, start + 1):
                user = interaction.guild.get_member(int(user_id))
                name = user.display_name if user else f"User {user_id}"
                description += f"**#{i} {name}**\n💎 Reputation: {data['rep']}\n\n"
            
            embed.description = description
            embed.set_footer(text=f"Page {page + 1}/{pages}")
            return embed

        class RepLeaderboardView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=60)
                self.current_page = 0

            @discord.ui.button(label="Previous", style=discord.ButtonStyle.primary, disabled=True)
            async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                self.current_page -= 1
                self.children[0].disabled = self.current_page == 0
                self.children[1].disabled = self.current_page == pages - 1
                await interaction.response.edit_message(embed=create_embed(self.current_page), view=self)

            @discord.ui.button(label="Next", style=discord.ButtonStyle.primary)
            async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                self.current_page += 1
                self.children[0].disabled = self.current_page == 0
                self.children[1].disabled = self.current_page == pages - 1
                await interaction.response.edit_message(embed=create_embed(self.current_page), view=self)

        view = RepLeaderboardView()
        if pages <= 1:
            view.children[0].disabled = True
            view.children[1].disabled = True
            
        await interaction.response.send_message(embed=create_embed(0), view=view)

async def setup(bot):
    await bot.add_cog(ReputationCog(bot))
