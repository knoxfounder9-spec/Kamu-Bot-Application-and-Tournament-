import discord
from discord import app_commands
from discord.ext import commands
import sqlite3
import os
import asyncio

DB_FILE = 'tickets.db'

class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.danger, custom_id="ticket_close", emoji="🔒")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Ticket will close in 5 seconds...", ephemeral=True)
        await asyncio.sleep(5)
        try:
            await interaction.channel.delete()
        except discord.NotFound:
            pass # Channel already deleted

class TicketSelect(discord.ui.Select):
    def __init__(self, bot):
        options = [
            discord.SelectOption(label="Claim Reward Ticket", value="reward", description="Claim a reward you have earned", emoji="🎁"),
            discord.SelectOption(label="Member Report Ticket", value="report_member", description="Report a member for rule violations", emoji="🛡️"),
            discord.SelectOption(label="Staff Report Ticket", value="report_staff", description="Report a staff member", emoji="🚨"),
            discord.SelectOption(label="Warn Appeal Ticket", value="appeal_warn", description="Appeal a warning you received", emoji="📜"),
        ]
        super().__init__(
            placeholder="Select a ticket category...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="ticket_select"
        )
        self.bot = bot

    async def callback(self, interaction: discord.Interaction):
        # Defer the interaction to prevent timeout while creating channel
        await interaction.response.defer(ephemeral=True)
        
        guild_id = interaction.guild.id
        user = interaction.user
        ticket_type = self.values[0]

        # 1. Get Staff Role ID from DB
        staff_role_id = None
        try:
            with sqlite3.connect(DB_FILE) as conn:
                c = conn.cursor()
                c.execute("SELECT staff_role_id FROM guild_configs WHERE guild_id = ?", (guild_id,))
                result = c.fetchone()
                if result:
                    staff_role_id = result[0]
        except Exception as e:
            print(f"Database error: {e}")

        staff_role = interaction.guild.get_role(staff_role_id) if staff_role_id else None

        # Fallback: Try to find role by name "┃Kamu - Ticket Support"
        if not staff_role:
            staff_role = discord.utils.get(interaction.guild.roles, name="┃Kamu - Ticket Support")

        # 2. Create Channel
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            interaction.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }

        if staff_role:
            overwrites[staff_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        category_name = ticket_type.replace("_", "-")
        channel_name = f"ticket-{user.name}-{category_name}"
        
        # Get the specific category
        category = interaction.guild.get_channel(1480180275920244910)

        if not category:
            # Fallback if category not found (e.g. wrong ID or bot doesn't have access)
            category = interaction.channel.category if hasattr(interaction.channel, 'category') else None

        try:
            ticket_channel = await interaction.guild.create_text_channel(
                name=channel_name,
                overwrites=overwrites,
                category=category,
                reason=f"Ticket created by {user.name}"
            )
        except Exception as e:
            await interaction.followup.send(f"Failed to create ticket channel: {e}", ephemeral=True)
            return

        # 3. Send Welcome Message
        staff_ping = staff_role.mention if staff_role else "Staff"
        
        # Improved Welcome Message
        embed = discord.Embed(
            title=f"🎫 {ticket_type.replace('_', ' ').title()}",
            description=f"Hello {user.mention}!\n\n"
                        f"Thank you for reaching out. {staff_ping} has been notified and will be with you shortly.\n\n"
                        f"**Please provide the following details:**\n"
                        f"• A clear description of your request or issue.\n"
                        f"• Any relevant proof or screenshots.\n\n"
                        f"Please be patient, we will assist you as soon as possible.",
            color=discord.Color.red()
        )
        embed.set_footer(text="Click the button below to close this ticket.")

        await ticket_channel.send(content=f"{staff_ping}", embed=embed, view=TicketControlView())

        await interaction.followup.send(f"Ticket created: {ticket_channel.mention}", ephemeral=True)

class TicketView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.add_item(TicketSelect(bot))

class TicketsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.init_db()

    def init_db(self):
        with sqlite3.connect(DB_FILE) as conn:
            c = conn.cursor()
            c.execute('''CREATE TABLE IF NOT EXISTS guild_configs
                         (guild_id INTEGER PRIMARY KEY, staff_role_id INTEGER)''')
            conn.commit()

    async def cog_load(self):
        self.bot.add_view(TicketView(self.bot))
        self.bot.add_view(TicketControlView())

    @app_commands.command(name="ticketstaffrole", description="Set the staff role for tickets")
    @app_commands.describe(role="The role to ping when a ticket is opened")
    @app_commands.checks.has_permissions(administrator=True)
    async def ticket_staff_role(self, interaction: discord.Interaction, role: discord.Role):
        with sqlite3.connect(DB_FILE) as conn:
            c = conn.cursor()
            c.execute("INSERT OR REPLACE INTO guild_configs (guild_id, staff_role_id) VALUES (?, ?)", (interaction.guild.id, role.id))
            conn.commit()
        
        await interaction.response.send_message(f"Ticket staff role set to {role.mention}", ephemeral=True)

    @app_commands.command(name="ticketpanel", description="Create the ticket panel")
    @app_commands.checks.has_permissions(administrator=True)
    async def ticket_panel(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="Support Tickets",
            description="Please select the appropriate category below to open a ticket.\n\n"
                        "**Categories:**\n"
                        "🎁 **Claim Reward Ticket** - Claim a reward you have earned.\n"
                        "🛡️ **Member Report Ticket** - Report a member for rule violations.\n"
                        "🚨 **Staff Report Ticket** - Report a staff member.\n"
                        "📜 **Warn Appeal Ticket** - Appeal a warning you received.\n\n"
                        "Our staff team will be with you shortly.",
            color=discord.Color.red()
        )
        
        view = TicketView(self.bot)
        await interaction.channel.send(embed=embed, view=view)
        await interaction.response.send_message("Ticket panel created!", ephemeral=True)

    @ticket_staff_role.error
    async def ticket_staff_role_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("You need Administrator permissions to use this command.", ephemeral=True)

    @ticket_panel.error
    async def ticket_panel_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("You need Administrator permissions to use this command.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(TicketsCog(bot))
