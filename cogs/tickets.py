import discord
from discord import app_commands
from discord.ext import commands
import sqlite3
import os

DB_FILE = 'tickets.db'

class TicketSelect(discord.ui.Select):
    def __init__(self, bot):
        options = [
            discord.SelectOption(label="Claim Reward Ticket", value="reward", description="Claim a reward you have earned", emoji="🎁"),
            discord.SelectOption(label="Member Report Ticket", value="report_member", description="Report a member for rule violations", emoji="🛡️"),
            discord.SelectOption(label="Staff Report Ticket", value="report_staff", description="Report a staff member", emoji="🚨"),
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
        
        # Check if a category exists for tickets, otherwise create in current category or top level
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
        
        welcome_msg = f"{user.mention}\n{staff_ping} will assist you slowly. Please be patient or something good"
        
        embed = discord.Embed(
            title=f"{ticket_type.replace('_', ' ').title()}",
            description="Please describe your issue in detail. Support will be with you shortly.",
            color=discord.Color.red()
        )

        await ticket_channel.send(content=welcome_msg, embed=embed)

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
                        "🚨 **Staff Report Ticket** - Report a staff member.\n\n"
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
