import discord
from discord import app_commands
from discord.ext import commands
import json
import os
import math

GRIND_STATS_FILE = 'grind_stats.json'
GRIND_TEAM_ROLE_NAME = "Grind Team"

def load_grind_stats():
    if not os.path.exists(GRIND_STATS_FILE):
        return {}
    with open(GRIND_STATS_FILE, 'r') as f:
        return json.load(f)

def save_grind_stats(stats):
    with open(GRIND_STATS_FILE, 'w') as f:
        json.dump(stats, f, indent=4)

class GrindingCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def get_user_stats(self, user_id):
        stats = load_grind_stats()
        return stats.get(str(user_id), {"wins": 0, "elo": 0})

    def update_user_stats(self, user_id, wins_delta=0, elo_delta=0):
        stats = load_grind_stats()
        user_key = str(user_id)
        if user_key not in stats:
            stats[user_key] = {"wins": 0, "elo": 0}
        
        stats[user_key]["wins"] += wins_delta
        stats[user_key]["elo"] += elo_delta
        
        # Prevent negative stats? Maybe elo can be negative, but wins probably not.
        if stats[user_key]["wins"] < 0: stats[user_key]["wins"] = 0
        
        save_grind_stats(stats)
        return stats[user_key]

    @app_commands.command(name="helpgrinding", description="Request help from the Grind Team (Creates a private channel)")
    async def helpgrinding(self, interaction: discord.Interaction):
        guild = interaction.guild
        user = interaction.user
        
        # Find Grind Team role
        grind_role = discord.utils.get(guild.roles, name=GRIND_TEAM_ROLE_NAME)
        if not grind_role:
            # Try to find it case-insensitive if exact match fails
            for r in guild.roles:
                if r.name.lower() == GRIND_TEAM_ROLE_NAME.lower():
                    grind_role = r
                    break
        
        if not grind_role:
            await interaction.response.send_message(f"Error: Role '{GRIND_TEAM_ROLE_NAME}' not found in this server.", ephemeral=True)
            return

        # Create permissions
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            grind_role: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }

        # Create channel
        category = discord.utils.get(guild.categories, name="Grind Tickets")
        if not category:
            category = await guild.create_category("Grind Tickets")

        channel_name = f"grind-help-{user.name}"
        channel = await guild.create_text_channel(channel_name, category=category, overwrites=overwrites)

        await interaction.response.send_message(f"Created a private channel for you: {channel.mention}", ephemeral=True)
        await channel.send(f"{user.mention} needs help! {grind_role.mention}, please assist.")

    # --- Win Management ---

    @app_commands.command(name="addwin", description="Add wins to a user (1 win = +5 Elo)")
    @app_commands.describe(user="The user to add wins to", amount="Number of wins")
    @app_commands.checks.has_any_role(GRIND_TEAM_ROLE_NAME)
    async def addwin(self, interaction: discord.Interaction, user: discord.User, amount: int):
        elo_change = amount * 5
        new_stats = self.update_user_stats(user.id, wins_delta=amount, elo_delta=elo_change)
        await interaction.response.send_message(f"Added **{amount}** wins to {user.mention}. (+{elo_change} Elo)\nTotal Wins: {new_stats['wins']} | Total Elo: {new_stats['elo']}")

    @app_commands.command(name="removewin", description="Remove wins from a user (1 win = -5 Elo)")
    @app_commands.describe(user="The user to remove wins from", amount="Number of wins")
    @app_commands.checks.has_any_role(GRIND_TEAM_ROLE_NAME)
    async def removewin(self, interaction: discord.Interaction, user: discord.User, amount: int):
        elo_change = -(amount * 5)
        new_stats = self.update_user_stats(user.id, wins_delta=-amount, elo_delta=elo_change)
        await interaction.response.send_message(f"Removed **{amount}** wins from {user.mention}. ({elo_change} Elo)\nTotal Wins: {new_stats['wins']} | Total Elo: {new_stats['elo']}")

    # --- Elo Management ---

    @app_commands.command(name="addelo", description="Add Elo to a user directly")
    @app_commands.describe(user="The user to add Elo to", amount="Amount of Elo")
    @app_commands.checks.has_any_role(GRIND_TEAM_ROLE_NAME)
    async def addelo(self, interaction: discord.Interaction, user: discord.User, amount: int):
        new_stats = self.update_user_stats(user.id, elo_delta=amount)
        await interaction.response.send_message(f"Added **{amount}** Elo to {user.mention}.\nTotal Wins: {new_stats['wins']} | Total Elo: {new_stats['elo']}")

    @app_commands.command(name="removeelo", description="Remove Elo from a user directly")
    @app_commands.describe(user="The user to remove Elo from", amount="Amount of Elo")
    @app_commands.checks.has_any_role(GRIND_TEAM_ROLE_NAME)
    async def removeelo(self, interaction: discord.Interaction, user: discord.User, amount: int):
        new_stats = self.update_user_stats(user.id, elo_delta=-amount)
        await interaction.response.send_message(f"Removed **{amount}** Elo from {user.mention}.\nTotal Wins: {new_stats['wins']} | Total Elo: {new_stats['elo']}")

    # --- Leaderboard ---

    @app_commands.command(name="leaderboard", description="Show the Grind Leaderboard")
    async def leaderboard(self, interaction: discord.Interaction):
        stats = load_grind_stats()
        if not stats:
            await interaction.response.send_message("No stats available yet.", ephemeral=True)
            return

        # Sort by Elo descending
        sorted_stats = sorted(stats.items(), key=lambda item: item[1]['elo'], reverse=True)
        
        items_per_page = 8
        pages = math.ceil(len(sorted_stats) / items_per_page)
        
        current_page = 0
        
        def create_embed(page):
            start = page * items_per_page
            end = start + items_per_page
            current_page_data = sorted_stats[start:end]
            
            embed = discord.Embed(title="🔥 Grind Leaderboard 🔥", color=discord.Color.gold())
            description = ""
            for i, (user_id, data) in enumerate(current_page_data, start + 1):
                user = interaction.guild.get_member(int(user_id))
                name = user.display_name if user else f"User {user_id}"
                description += f"**#{i} {name}**\n🏆 Wins: {data['wins']} | ⚡ Elo: {data['elo']}\n\n"
            
            embed.description = description
            embed.set_footer(text=f"Page {page + 1}/{pages}")
            return embed

        class LeaderboardView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=60)
                self.current_page = 0

            @discord.ui.button(label="Previous", style=discord.ButtonStyle.primary, disabled=True)
            async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                self.current_page -= 1
                await self.update_message(interaction)

            @discord.ui.button(label="Next", style=discord.ButtonStyle.primary)
            async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                self.current_page += 1
                await self.update_message(interaction)

            async def update_message(self, interaction: discord.Interaction):
                self.children[0].disabled = self.current_page == 0
                self.children[1].disabled = self.current_page == pages - 1
                await interaction.response.edit_message(embed=create_embed(self.current_page), view=self)

        view = LeaderboardView()
        if pages <= 1:
            view.children[0].disabled = True
            view.children[1].disabled = True
            
        await interaction.response.send_message(embed=create_embed(0), view=view)

async def setup(bot):
    await bot.add_cog(GrindingCog(bot))
