import discord
from discord import app_commands
from discord.ext import commands
import sqlite3
import os
import json
import math

DB_FILE = 'reputation.db'
JSON_FILE = 'reputation.json'

class ReputationCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.init_db()
        self.migrate_json()

    def init_db(self):
        with sqlite3.connect(DB_FILE) as conn:
            c = conn.cursor()
            c.execute('''CREATE TABLE IF NOT EXISTS reputation
                         (user_id INTEGER PRIMARY KEY, rep INTEGER)''')
            conn.commit()

    def migrate_json(self):
        if os.path.exists(JSON_FILE):
            try:
                print("Migrating reputation.json to database...")
                with open(JSON_FILE, 'r') as f:
                    data = json.load(f)
                
                with sqlite3.connect(DB_FILE) as conn:
                    c = conn.cursor()
                    for uid, info in data.items():
                        c.execute("INSERT OR IGNORE INTO reputation (user_id, rep) VALUES (?, ?)", 
                                  (int(uid), info.get('rep', 0)))
                    conn.commit()
                
                os.rename(JSON_FILE, JSON_FILE + '.bak')
                print("Migration complete. Renamed reputation.json to reputation.json.bak")
            except Exception as e:
                print(f"Error migrating reputation.json: {e}")

    def update_rep(self, user_id, amount):
        with sqlite3.connect(DB_FILE) as conn:
            c = conn.cursor()
            c.execute("SELECT rep FROM reputation WHERE user_id = ?", (user_id,))
            result = c.fetchone()
            current_rep = result[0] if result else 0
            new_rep = current_rep + amount
            c.execute("INSERT OR REPLACE INTO reputation (user_id, rep) VALUES (?, ?)", (user_id, new_rep))
            conn.commit()
            return new_rep

    def get_all_rep(self):
        with sqlite3.connect(DB_FILE) as conn:
            c = conn.cursor()
            c.execute("SELECT user_id, rep FROM reputation ORDER BY rep DESC")
            return c.fetchall()

    @commands.command(name="rep")
    async def rep_command(self, ctx, amount: int, user: discord.User):
        if ctx.author.id != 1313484931892117524:
            await ctx.send("You do not have permission to use this command.")
            return

        if user.id == ctx.author.id:
            await ctx.send("You cannot modify your own reputation!")
            return
        
        new_rep = self.update_rep(user.id, amount)
        action = "given to" if amount >= 0 else "removed from"
        await ctx.send(f"**{amount} Reputation** {action} {user.mention} (`{user.id}`)! They now have **{new_rep}** rep.")

    @app_commands.command(name="repleaderboard", description="Show the Reputation Leaderboard")
    async def repleaderboard(self, interaction: discord.Interaction):
        stats = self.get_all_rep()
        if not stats:
            await interaction.response.send_message("No reputation stats available yet.", ephemeral=True)
            return

        items_per_page = 8
        pages = math.ceil(len(stats) / items_per_page)
        
        def create_embed(page):
            start = page * items_per_page
            end = start + items_per_page
            current_page_data = stats[start:end]
            
            embed = discord.Embed(title="🌟 Reputation Leaderboard 🌟", color=discord.Color.purple())
            description = ""
            for i, (user_id, rep) in enumerate(current_page_data, start + 1):
                user = interaction.guild.get_member(user_id)
                name = user.display_name if user else f"User {user_id}"
                description += f"**#{i} {name}**\n💎 Reputation: {rep}\n\n"
            
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
