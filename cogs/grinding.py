import discord
from discord import app_commands
from discord.ext import commands
import json
import os
import math
import datetime
import time
import asyncio

GRIND_STATS_FILE = 'grind_stats.json'
GRIND_BLACKLIST_FILE = 'grind_blacklist.json'
GRIND_TEAM_ROLE_ID = 1477359005339877446
GRIND_TICKETS_CATEGORY_ID = 1478678699032449076

def load_grind_stats():
    if not os.path.exists(GRIND_STATS_FILE):
        return {}
    with open(GRIND_STATS_FILE, 'r') as f:
        return json.load(f)

def save_grind_stats(stats):
    with open(GRIND_STATS_FILE, 'w') as f:
        json.dump(stats, f, indent=4)

def load_blacklist():
    if not os.path.exists(GRIND_BLACKLIST_FILE):
        return {}
    with open(GRIND_BLACKLIST_FILE, 'r') as f:
        return json.load(f)

def save_blacklist(blacklist):
    with open(GRIND_BLACKLIST_FILE, 'w') as f:
        json.dump(blacklist, f, indent=4)

class CloseTicketView(discord.ui.View):
    def __init__(self, grind_role_id):
        super().__init__(timeout=None)
        self.grind_role_id = grind_role_id

    @discord.ui.button(label="Add Person", style=discord.ButtonStyle.primary, emoji="👤", custom_id="ticket_add_person")
    async def add_person(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Check permissions: Admin or Grind Team Role
        user = interaction.user
        is_admin = False
        has_role = False
        
        if isinstance(user, discord.Member):
            is_admin = user.guild_permissions.administrator
            has_role = any(role.id == self.grind_role_id for role in user.roles)
        
        if not (is_admin or has_role):
            await interaction.response.send_message("Only Admins or the Grind Team can add people to this ticket.", ephemeral=True)
            return

        # Create a view with a user select
        class UserSelectView(discord.ui.View):
            def __init__(self, channel):
                super().__init__(timeout=60)
                self.channel = channel

            @discord.ui.select(cls=discord.ui.UserSelect, placeholder="Select a user to add...")
            async def select_user(self, interaction: discord.Interaction, select: discord.ui.UserSelect):
                target_user = select.values[0]
                if isinstance(target_user, discord.Member):
                    await self.channel.set_permissions(target_user, read_messages=True, send_messages=True)
                    await interaction.response.send_message(f"✅ Added {target_user.mention} to the ticket.", ephemeral=True)
                    await self.channel.send(f"👤 {target_user.mention} has been added to the ticket by {interaction.user.mention}.")
                else:
                    await interaction.response.send_message("Could not add user. Make sure they are in the server.", ephemeral=True)

        await interaction.response.send_message("Select a user to add to this ticket:", view=UserSelectView(interaction.channel), ephemeral=True)

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="ticket_close")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Check permissions: Admin or Grind Team Role or Ticket Owner
        user = interaction.user
        is_admin = False
        has_role = False
        is_ticket_owner = False
        
        if isinstance(user, discord.Member):
            is_admin = user.guild_permissions.administrator
            has_role = any(role.id == self.grind_role_id for role in user.roles)
            
            # Check if user is the ticket owner (based on channel name convention)
            # Channel name format: username-type-number
            sanitized_name = user.name.lower().replace(" ", "-")
            if interaction.channel.name.startswith(sanitized_name):
                is_ticket_owner = True
        
        if not (is_admin or has_role or is_ticket_owner):
            await interaction.response.send_message("Only Admins, the Grind Team, or the ticket owner can close this ticket.", ephemeral=True)
            return
        
        await interaction.response.send_message("Closing ticket in 5 seconds...")
        await asyncio.sleep(5)
        try:
            await interaction.channel.delete()
        except:
            pass

class ApplicationReviewView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=None)
        self.user_id = user_id

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success, custom_id="app_accept")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        try:
            user = await interaction.client.fetch_user(self.user_id)
            await user.send("✅ Your grinding application has been **ACCEPTED**!")
            await interaction.followup.send(f"Application accepted by {interaction.user.mention}.")
            
            # Disable buttons
            for child in self.children:
                if child.custom_id in ["app_accept", "app_reject"]:
                    child.disabled = True
            await interaction.message.edit(view=self)
        except Exception as e:
            await interaction.followup.send(f"Error: {e}", ephemeral=True)

    @discord.ui.button(label="Reject", style=discord.ButtonStyle.danger, custom_id="app_reject")
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        try:
            user = await interaction.client.fetch_user(self.user_id)
            await user.send("❌ Your grinding application has been **REJECTED**.")
            await interaction.followup.send(f"Application rejected by {interaction.user.mention}.")
            
            # Disable buttons
            for child in self.children:
                if child.custom_id in ["app_accept", "app_reject"]:
                    child.disabled = True
            await interaction.message.edit(view=self)
        except Exception as e:
            await interaction.followup.send(f"Error: {e}", ephemeral=True)

    @discord.ui.button(label="Notify Login", style=discord.ButtonStyle.primary, custom_id="app_login_notify", emoji="🔔")
    async def notify_login(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        try:
            user = await interaction.client.fetch_user(self.user_id)
            await user.send("🔔 **Update:** A grinder is logging into your account now.")
            await interaction.followup.send(f"Login notification sent to user.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"Error: {e}", ephemeral=True)

class AccountGrindModal(discord.ui.Modal, title="Account Grind Application"):
    username = discord.ui.TextInput(label="Roblox Username", placeholder="Enter your Roblox username")
    password = discord.ui.TextInput(label="Roblox Password", placeholder="Enter your Roblox password")
    request = discord.ui.TextInput(label="Service Request", placeholder="What specific grinding services do you require?", style=discord.TextStyle.paragraph)
    two_fa = discord.ui.TextInput(label="2FA Status", placeholder="Is Two-Step Verification enabled? (Yes/No)")
    agreements = discord.ui.TextInput(label="Terms Acknowledgement", placeholder="Confirm: Trust, 3-5 Day Wait, Extra Cost (Yes/No)", style=discord.TextStyle.paragraph)

    async def on_submit(self, interaction: discord.Interaction):
        target_channel_id = 1313484931892117524
        target_channel = interaction.guild.get_channel(target_channel_id)
        
        if not target_channel:
             await interaction.response.send_message("Error: Application channel not found (ID: 1313484931892117524).", ephemeral=True)
             return

        embed = discord.Embed(title="📝 New Account Grind Application", color=discord.Color.blue(), timestamp=datetime.datetime.now())
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="User", value=interaction.user.mention, inline=False)
        embed.add_field(name="Roblox Username", value=self.username.value, inline=True)
        embed.add_field(name="Roblox Password", value=f"||{self.password.value}||", inline=True)
        embed.add_field(name="Request", value=self.request.value, inline=False)
        embed.add_field(name="2FA Status", value=self.two_fa.value, inline=True)
        embed.add_field(name="Terms Agreement", value=self.agreements.value, inline=False)
        
        await target_channel.send(embed=embed, view=ApplicationReviewView(interaction.user.id))
        await interaction.response.send_message("Your application has been submitted successfully!", ephemeral=True)

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

    async def get_grind_category(self, guild):
        category = guild.get_channel(GRIND_TICKETS_CATEGORY_ID)
        if not category:
            try:
                category = await guild.fetch_channel(GRIND_TICKETS_CATEGORY_ID)
            except:
                pass
        
        if not isinstance(category, discord.CategoryChannel):
            category = discord.utils.get(guild.categories, name="Grind Tickets")
            
        if not category:
            category = await guild.create_category("Grind Tickets")
            
        return category

    @app_commands.command(name="helpgrinding", description="Request help from the Grind Team")
    async def helpgrinding(self, interaction: discord.Interaction):
        user = interaction.user
        
        # Check Blacklist
        blacklist = load_blacklist()
        if str(user.id) in blacklist:
            expiry_timestamp = blacklist[str(user.id)]
            if time.time() < expiry_timestamp:
                # Still blacklisted
                expiry_dt = datetime.datetime.fromtimestamp(expiry_timestamp)
                relative_time = discord.utils.format_dt(expiry_dt, style="R")
                await interaction.response.send_message(f"You are blacklisted from creating grind tickets until {relative_time}.", ephemeral=True)
                return
            else:
                # Expired, remove from blacklist
                del blacklist[str(user.id)]
                save_blacklist(blacklist)

        # Check if user already has an open ticket
        guild = interaction.guild
        category = await self.get_grind_category(guild)
        
        if category:
            for channel in category.text_channels:
                # Check if channel name starts with user's name (simple check)
                # A more robust way would be to store ticket owners in a DB, but name check works for now
                if channel.name.startswith(f"{user.name.lower()}-"):
                    await interaction.response.send_message(f"You already have an open ticket: {channel.mention}. Please close it before opening a new one.", ephemeral=True)
                    return

        # Create a view with a select menu
        class GrindTypeView(discord.ui.View):
            def __init__(self, bot_ref):
                super().__init__(timeout=60)
                self.bot_ref = bot_ref

            @discord.ui.select(
                placeholder="Select the type of help you need...",
                options=[
                    discord.SelectOption(label="WorldBoss", description="Help with World Bosses", emoji="🌍"),
                    discord.SelectOption(label="Quests", description="Help with Quests", emoji="📜"),
                    discord.SelectOption(label="Raids", description="Help with Raids", emoji="⚔️"),
                    discord.SelectOption(label="Account Grind", description="Apply for Account Grinding", emoji="👤"),
                ]
            )
            async def select_callback(self, interaction: discord.Interaction, select: discord.ui.Select):
                grind_type = select.values[0]
                
                if grind_type == "Account Grind":
                    await interaction.response.send_modal(AccountGrindModal())
                    return

                guild = interaction.guild
                user = interaction.user
                
                # Find Grind Team role by ID
                grind_role = guild.get_role(GRIND_TEAM_ROLE_ID)
                
                # Create permissions
                # User and Bot get access. Grind Team role also gets access so they can see it.
                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(read_messages=False),
                    user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                    guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
                }
                
                if grind_role:
                    overwrites[grind_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

                # Get the correct category
                category = await self.bot_ref.get_cog("GrindingCog").get_grind_category(guild)

                # Generate channel name: user-type-number
                count = 1
                base_name = f"{user.name}-{grind_type}".lower().replace(" ", "-")
                for channel in category.text_channels:
                    if channel.name.startswith(base_name):
                        count += 1
                
                channel_name = f"{base_name}-{count}"
                
                try:
                    channel = await guild.create_text_channel(channel_name, category=category, overwrites=overwrites)
                    await interaction.response.send_message(f"Ticket created: {channel.mention}", ephemeral=True)
                    
                    # Ping the role inside the channel
                    role_mention = grind_role.mention if grind_role else "@Grind Team"
                    
                    await channel.send(f"{role_mention}\nYou have been summoned by {user.mention} for help with **{grind_type}**.", view=CloseTicketView(GRIND_TEAM_ROLE_ID))
                    
                except Exception as e:
                    await interaction.response.send_message(f"Failed to create channel: {e}", ephemeral=True)

        await interaction.response.send_message("Please select the type of grinding help you need:", view=GrindTypeView(self.bot), ephemeral=True)

    @app_commands.command(name="helpblacklist", description="Blacklist a user from creating grind tickets")
    @app_commands.describe(user="The user to blacklist", hours="Duration in hours")
    @app_commands.checks.has_permissions(administrator=True)
    async def helpblacklist(self, interaction: discord.Interaction, user: discord.User, hours: int):
        blacklist = load_blacklist()
        
        # Calculate expiry timestamp
        expiry_time = time.time() + (hours * 3600)
        blacklist[str(user.id)] = expiry_time
        
        save_blacklist(blacklist)
        
        expiry_dt = datetime.datetime.fromtimestamp(expiry_time)
        relative_time = discord.utils.format_dt(expiry_dt, style="R")
        
        await interaction.response.send_message(f"🚫 {user.mention} has been blacklisted from creating grind tickets for **{hours} hours** (until {relative_time}).")

    @app_commands.command(name="helpingclose", description="Close the current ticket channel")
    async def helpingclose(self, interaction: discord.Interaction):
        # Check if we are in a ticket channel (under Grind Tickets category)
        if not interaction.channel.category or (interaction.channel.category.id != GRIND_TICKETS_CATEGORY_ID and interaction.channel.category.name != "Grind Tickets"):
             await interaction.response.send_message("This command can only be used in a Grind Ticket channel.", ephemeral=True)
             return

        # Check permissions: Admin or Grind Team Role or Ticket Owner
        user = interaction.user
        is_admin = False
        has_role = False
        is_ticket_owner = False
        
        if isinstance(user, discord.Member):
            is_admin = user.guild_permissions.administrator
            has_role = any(role.id == GRIND_TEAM_ROLE_ID for role in user.roles)
            
            # Check if user is the ticket owner (based on channel name convention)
            # Channel name format: username-type-number
            sanitized_name = user.name.lower().replace(" ", "-")
            if interaction.channel.name.startswith(sanitized_name):
                is_ticket_owner = True
        
        if not (is_admin or has_role or is_ticket_owner):
            await interaction.response.send_message("Only Admins, the Grind Team, or the ticket owner can close this ticket.", ephemeral=True)
            return

        await interaction.response.send_message("Closing ticket in 5 seconds...")
        await asyncio.sleep(5)
        try:
            await interaction.channel.delete()
        except:
            pass

    # --- Win Management ---

    @app_commands.command(name="addwin", description="Add wins to a user (1 win = +5 Elo)")
    @app_commands.describe(user="The user to add wins to", amount="Number of wins")
    @app_commands.checks.has_permissions(administrator=True)
    async def addwin(self, interaction: discord.Interaction, user: discord.User, amount: int):
        elo_change = amount * 5
        new_stats = self.update_user_stats(user.id, wins_delta=amount, elo_delta=elo_change)
        await interaction.response.send_message(f"Added **{amount}** wins to {user.mention}. (+{elo_change} Elo)\nTotal Wins: {new_stats['wins']} | Total Elo: {new_stats['elo']}")

    @app_commands.command(name="removewin", description="Remove wins from a user (1 win = -5 Elo)")
    @app_commands.describe(user="The user to remove wins from", amount="Number of wins")
    @app_commands.checks.has_permissions(administrator=True)
    async def removewin(self, interaction: discord.Interaction, user: discord.User, amount: int):
        elo_change = -(amount * 5)
        new_stats = self.update_user_stats(user.id, wins_delta=-amount, elo_delta=elo_change)
        await interaction.response.send_message(f"Removed **{amount}** wins from {user.mention}. ({elo_change} Elo)\nTotal Wins: {new_stats['wins']} | Total Elo: {new_stats['elo']}")

    # --- Elo Management ---

    @app_commands.command(name="addelo", description="Add Elo to a user directly")
    @app_commands.describe(user="The user to add Elo to", amount="Amount of Elo")
    @app_commands.checks.has_permissions(administrator=True)
    async def addelo(self, interaction: discord.Interaction, user: discord.User, amount: int):
        new_stats = self.update_user_stats(user.id, elo_delta=amount)
        await interaction.response.send_message(f"Added **{amount}** Elo to {user.mention}.\nTotal Wins: {new_stats['wins']} | Total Elo: {new_stats['elo']}")

    @app_commands.command(name="removeelo", description="Remove Elo from a user directly")
    @app_commands.describe(user="The user to remove Elo from", amount="Amount of Elo")
    @app_commands.checks.has_permissions(administrator=True)
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
    bot.add_view(CloseTicketView(GRIND_TEAM_ROLE_ID))
    await bot.add_cog(GrindingCog(bot))
