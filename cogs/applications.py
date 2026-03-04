import discord
from discord import app_commands, ui
from discord.ext import commands
import os
import json

# --- Constants ---
LOG_CHANNEL_ID = os.getenv('LOG_CHANNEL_ID')
ROLES_FILE = 'roles.json'
APP_STATUS_FILE = 'app_status.json'
PANEL_CONFIG_FILE = 'panel_config.json'

# --- Helper Functions for Roles & Status ---
def load_roles():
    if not os.path.exists(ROLES_FILE):
        return {}
    with open(ROLES_FILE, 'r') as f:
        return json.load(f)

def save_roles(roles_data):
    with open(ROLES_FILE, 'w') as f:
        json.dump(roles_data, f, indent=4)

def get_role_id(guild_id, app_type):
    roles_data = load_roles()
    return roles_data.get(str(guild_id), {}).get(app_type)

def load_app_status():
    if not os.path.exists(APP_STATUS_FILE):
        return {}
    with open(APP_STATUS_FILE, 'r') as f:
        return json.load(f)

def save_app_status(status_data):
    with open(APP_STATUS_FILE, 'w') as f:
        json.dump(status_data, f, indent=4)

def get_app_status(guild_id, app_type):
    status_data = load_app_status()
    # Default to "Open" if not set
    return status_data.get(str(guild_id), {}).get(app_type, "Open")

def load_panel_config():
    if not os.path.exists(PANEL_CONFIG_FILE):
        return {}
    with open(PANEL_CONFIG_FILE, 'r') as f:
        return json.load(f)

def save_panel_config(config_data):
    with open(PANEL_CONFIG_FILE, 'w') as f:
        json.dump(config_data, f, indent=4)

def generate_panel_embeds(guild_id):
    status_grind = get_app_status(guild_id, "Grind Team")
    status_recruiter = get_app_status(guild_id, "Recruiter Team")
    status_trainers = get_app_status(guild_id, "Trainers")
    status_support = get_app_status(guild_id, "Support Team")

    def get_emoji(status):
        return "🟩" if status == "Open" else "🟥"
    
    # Custom color #740000
    color = discord.Color.from_str("#740000")

    # Embed 1: General Info
    embed1 = discord.Embed(
        title="Kamu Guild Recruitment",
        description=(
            "### Welcome to the official recruitment portal for Kamu Guild.\n\n"
            "> Staff applications are a formal process that allows members of Kamu to apply for leadership and moderation roles within the guild. "
            "These applications help ensure that only responsible, dedicated, and capable members are selected to represent and support the community.\n\n"
            "> Take your time with your application to ensure it's made to the best of your capabilities, ensure it shows initiative, commitment, and a willingness to take on more responsibility.\n\n"
            "**Standard Requirements:**\n\n"
            "> - Must be 14+\n"
            "> - Active In the Discord\n"
            "> - Able to work in a team"
        ),
        color=color
    )

    # Embed 2: Status
    embed2 = discord.Embed(
        description=(
            "> We are seeking dedicated and skilled individuals to join our ranks. "
            "Please review the available positions below and select the role that best aligns with your expertise and interests.\n\n"
            "### Available Positions:\n"
            f"> • **Grind Team:** {get_emoji(status_grind)}\n"
            f"> • **Recruiter Team:** {get_emoji(status_recruiter)}\n"
            f"> • **Trainers:** {get_emoji(status_trainers)}\n"
            f"> • **Support Team:** {get_emoji(status_support)}\n\n"
            "> Select an option from the dropdown menu to begin your application process."
        ),
        color=color
    )
    embed2.set_footer(text="Kamu Guild • Kaizen")
    
    return [embed1, embed2]

# --- Admin Views ---

class ApplicationReviewView(ui.View):
    def __init__(self, applicant_id: int, app_type: str):
        super().__init__(timeout=None) # Persistent view for logs
        self.applicant_id = applicant_id
        self.app_type = app_type

    @ui.button(label="Accept", style=discord.ButtonStyle.success, custom_id="app_accept")
    async def accept_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()
        
        guild = interaction.guild
        member = guild.get_member(self.applicant_id)
        
        if not member:
            await interaction.followup.send("Member not found in the server.", ephemeral=True)
            return

        role_id = get_role_id(guild.id, self.app_type)
        role_added = False
        
        if role_id:
            role = guild.get_role(role_id)
            if role:
                try:
                    await member.add_roles(role)
                    role_added = True
                except discord.Forbidden:
                    await interaction.followup.send("I don't have permission to add that role.", ephemeral=True)
            else:
                await interaction.followup.send("Configured role not found.", ephemeral=True)
        
        # Update Embed
        embed = interaction.message.embeds[0]
        embed.color = discord.Color.green()
        embed.add_field(name="Status", value=f"Accepted by {interaction.user.mention}", inline=False)
        if role_added:
             embed.add_field(name="Role Action", value=f"Role {role.mention} added.", inline=False)
        
        # Disable buttons
        for item in self.children:
            item.disabled = True
        
        await interaction.message.edit(embed=embed, view=self)
        
        # Notify User
        try:
            await member.send(f"Congratulations! Your application for **{self.app_type}** in **{guild.name}** has been ACCEPTED!")
        except:
            pass
            
        await interaction.followup.send("Application accepted.", ephemeral=True)

    @ui.button(label="Reject", style=discord.ButtonStyle.danger, custom_id="app_reject")
    async def reject_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()
        
        guild = interaction.guild
        member = guild.get_member(self.applicant_id)
        
        # Update Embed
        embed = interaction.message.embeds[0]
        embed.color = discord.Color.red()
        embed.add_field(name="Status", value=f"Rejected by {interaction.user.mention}", inline=False)
        
        # Disable buttons
        for item in self.children:
            item.disabled = True
            
        await interaction.message.edit(embed=embed, view=self)
        
        # Notify User
        if member:
            try:
                await member.send(f"Your application for **{self.app_type}** in **{guild.name}** has been REJECTED.")
            except:
                pass
        
        await interaction.followup.send("Application rejected.", ephemeral=True)

# --- Modals ---

class GrindTeamModal(ui.Modal, title='Grind Team Application'):
    def __init__(self):
        super().__init__()

    level_progression = ui.TextInput(
        label='What is your current level and progression?',
        style=discord.TextStyle.short,
        placeholder='e.g., Lvl 50, just started late game...',
        required=True,
        max_length=100
    )
    
    game_knowledge = ui.TextInput(
        label='What areas of the game do you excel in?',
        style=discord.TextStyle.long,
        placeholder='Describe your game sense and what you are good at...',
        required=True,
        max_length=500
    )

    helping_experience = ui.TextInput(
        label='Have you guided others before? Describe.',
        style=discord.TextStyle.paragraph,
        placeholder='Have you guided others before? Describe...',
        required=True,
        max_length=500
    )

    availability = ui.TextInput(
        label='How many hours are you available weekly?',
        style=discord.TextStyle.short,
        placeholder='e.g., 10-15 hours/week',
        required=True,
        max_length=100
    )

    why_fit = ui.TextInput(
        label='Why do you think you are a good fit?',
        style=discord.TextStyle.paragraph,
        placeholder='What makes you suitable for the Grind Team?',
        required=True,
        max_length=500
    )

    async def on_submit(self, interaction: discord.Interaction):
        await send_application_log(interaction, "Grind Team", [
            ("Current Level / Progression", self.level_progression.value),
            ("Game Knowledge", self.game_knowledge.value),
            ("Helping Experience", self.helping_experience.value),
            ("Availability", self.availability.value),
            ("Why Fit", self.why_fit.value)
        ])

class RecruiterTeamModal(ui.Modal, title='Recruiter Team Application'):
    def __init__(self):
        super().__init__()

    motivation = ui.TextInput(
        label='Why do you want to join the Recruiter Team?',
        style=discord.TextStyle.paragraph,
        required=True
    )

    invites_count = ui.TextInput(
        label='How many invites do you currently have?',
        placeholder='10 invites required',
        style=discord.TextStyle.short,
        required=True
    )

    pitch = ui.TextInput(
        label='How would you pitch Kamu to a new player?',
        style=discord.TextStyle.paragraph,
        placeholder='Pitch to someone who never heard of it...',
        required=True
    )

    methods = ui.TextInput(
        label='What methods would you use to recruit?',
        style=discord.TextStyle.paragraph,
        placeholder='What methods would you use?',
        required=True
    )

    experience_activity = ui.TextInput(
        label='Do you have experience? How active are you?',
        style=discord.TextStyle.paragraph,
        placeholder='Previous exp? How active will you be?',
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        await send_application_log(interaction, "Recruiter Team", [
            ("Motivation", self.motivation.value),
            ("Invites Count", self.invites_count.value),
            ("Pitch", self.pitch.value),
            ("Methods", self.methods.value),
            ("Experience & Activity", self.experience_activity.value)
        ])

class SupportTeamModal(ui.Modal, title='Support Team Application'):
    def __init__(self):
        super().__init__()

    familiarity = ui.TextInput(
        label='How familiar are you with the server?',
        style=discord.TextStyle.paragraph,
        placeholder='Layout, channels, structure...',
        required=True
    )

    handling_confusion = ui.TextInput(
        label='How would you handle a confused member?',
        style=discord.TextStyle.paragraph,
        placeholder='How would you handle frustration?',
        required=True
    )

    experience = ui.TextInput(
        label='Have you assisted in other servers before?',
        style=discord.TextStyle.paragraph,
        placeholder='Have you assisted in other servers?',
        required=True
    )

    comm_style = ui.TextInput(
        label='How would you describe your comms style?',
        style=discord.TextStyle.short,
        placeholder='Describe your style...',
        required=True
    )

    activity_promo = ui.TextInput(
        label='How active are you & how to promote Kamu?',
        style=discord.TextStyle.paragraph,
        placeholder='Activity level? Ideas to promote/explain Kamu?',
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        await send_application_log(interaction, "Support Team", [
            ("Familiarity", self.familiarity.value),
            ("Handling Confusion", self.handling_confusion.value),
            ("Experience", self.experience.value),
            ("Communication Style", self.comm_style.value),
            ("Activity & Promotion", self.activity_promo.value)
        ])

class TrainersModalPart2(ui.Modal, title='Trainers App (Part 2/2)'):
    def __init__(self, part1_data):
        super().__init__()
        self.part1_data = part1_data

    organized_engaging = ui.TextInput(
        label='How would you keep training organized?',
        style=discord.TextStyle.paragraph,
        placeholder='How to keep it engaging?',
        required=True
    )

    disruptive_handling = ui.TextInput(
        label='How would you handle disruptive players?',
        style=discord.TextStyle.paragraph,
        placeholder='What if it becomes chaotic?',
        required=True
    )

    experience = ui.TextInput(
        label='Do you have previous trainer experience?',
        style=discord.TextStyle.paragraph,
        placeholder='State your experience...',
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        # Combine data
        # part1_data is a list of tuples
        full_data = self.part1_data + [
            ("Organized & Engaging", self.organized_engaging.value),
            ("Disruptive Handling", self.disruptive_handling.value),
            ("Experience", self.experience.value)
        ]
        
        await send_application_log(interaction, "Trainers", full_data)

class ContinueTrainersView(ui.View):
    def __init__(self, part1_data):
        super().__init__(timeout=600)
        self.part1_data = part1_data

    @ui.button(label="Continue to Part 2", style=discord.ButtonStyle.primary)
    async def continue_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(TrainersModalPart2(self.part1_data))

class TrainersModalPart1(ui.Modal, title='Trainers App (Part 1/2)'):
    def __init__(self):
        super().__init__()

    motivation = ui.TextInput(
        label='Why do you want to be a Trainer?',
        style=discord.TextStyle.paragraph,
        required=True
    )

    activity = ui.TextInput(
        label='Rate activity (1-10) & hosting freq?',
        style=discord.TextStyle.short,
        placeholder='Rate 1-10. How often can you host?',
        required=True
    )

    fair_ranking = ui.TextInput(
        label='How would you ensure fair ranking?',
        style=discord.TextStyle.paragraph,
        required=True
    )

    disagreement = ui.TextInput(
        label='How would you handle rank disagreements?',
        style=discord.TextStyle.paragraph,
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        part1_data = [
            ("Motivation", self.motivation.value),
            ("Activity", self.activity.value),
            ("Fair Ranking", self.fair_ranking.value),
            ("Disagreement Handling", self.disagreement.value)
        ]
        await interaction.response.send_message(
            "Part 1 received! Please click the button below to complete Part 2.",
            view=ContinueTrainersView(part1_data),
            ephemeral=True
        )

# --- Helper Functions ---

async def send_application_log(interaction: discord.Interaction, app_type: str, fields: list):
    embed = discord.Embed(
        title=f"New {app_type} Application",
        color=discord.Color.blue(),
        timestamp=interaction.created_at
    )
    embed.set_author(name=f"{interaction.user.name} ({interaction.user.id})", icon_url=interaction.user.display_avatar.url)
    embed.set_footer(text=f"User ID: {interaction.user.id}")
    
    for name, value in fields:
        embed.add_field(name=name, value=value, inline=False)

    # Try to find the log channel
    log_channel = None
    if LOG_CHANNEL_ID:
        try:
            log_channel = interaction.guild.get_channel(int(LOG_CHANNEL_ID))
        except:
            pass
    
    # Fallback: look for a channel named 'application-logs'
    if not log_channel:
        log_channel = discord.utils.get(interaction.guild.text_channels, name='application-logs')

    if log_channel:
        view = ApplicationReviewView(applicant_id=interaction.user.id, app_type=app_type)
        await log_channel.send(embed=embed, view=view)
        await interaction.response.send_message("Application submitted successfully!", ephemeral=True)
    else:
        await interaction.response.send_message("Application submitted! (Note: 'application-logs' channel not found, so admins might not see this immediately.)", ephemeral=True)


# --- Views ---

class ApplicationSelect(ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Grind Team App", description="Apply for the Grind Team", emoji="⚔️"),
            discord.SelectOption(label="Recruiter App", description="Apply for the Recruiter Team", emoji="📢"),
            discord.SelectOption(label="Trainers App", description="Apply to become a Trainer", emoji="🎓"),
            discord.SelectOption(label="Support Team App", description="Apply for the Support Team", emoji="🛡️"),
        ]
        super().__init__(placeholder="Select an application...", min_values=1, max_values=1, options=options, custom_id="application_select")

    async def callback(self, interaction: discord.Interaction):
        choice = self.values[0]
        guild_id = interaction.guild_id
        
        # Check status
        app_type_map = {
            "Grind Team App": "Grind Team",
            "Recruiter App": "Recruiter Team",
            "Trainers App": "Trainers",
            "Support Team App": "Support Team"
        }
        
        app_type = app_type_map.get(choice)
        if app_type:
            status = get_app_status(guild_id, app_type)
            if status == "Closed":
                await interaction.response.send_message(f"Sorry, applications for **{app_type}** are currently **CLOSED**.", ephemeral=True)
                return
        
        if choice == "Grind Team App":
            await interaction.response.send_modal(GrindTeamModal())
        elif choice == "Recruiter App":
            await interaction.response.send_modal(RecruiterTeamModal())
        elif choice == "Trainers App":
            await interaction.response.send_modal(TrainersModalPart1())
        elif choice == "Support Team App":
            await interaction.response.send_modal(SupportTeamModal())

class ApplicationView(ui.View):
    def __init__(self):
        super().__init__(timeout=None) # Persistent view
        self.add_item(ApplicationSelect())

# --- Cog ---

class Applications(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        self.bot.add_view(ApplicationView())

    @app_commands.command(name="panel", description="Creates the application panel")
    @app_commands.checks.has_permissions(administrator=True)
    async def panel(self, interaction: discord.Interaction):
        embeds = generate_panel_embeds(interaction.guild_id)
        embeds[0].set_thumbnail(url=interaction.guild.icon.url if interaction.guild.icon else None)
        
        await interaction.response.send_message(embeds=embeds, view=ApplicationView())
        
        # Save message info for auto-updates
        message = await interaction.original_response()
        config = load_panel_config()
        config[str(interaction.guild_id)] = {
            "channel_id": interaction.channel_id,
            "message_id": message.id
        }
        save_panel_config(config)

    @app_commands.command(name="setapp", description="Set the status of an application (Open/Closed)")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        app_type="The type of application",
        status="The status (Open or Closed)"
    )
    @app_commands.choices(app_type=[
        app_commands.Choice(name="Grind Team", value="Grind Team"),
        app_commands.Choice(name="Recruiter Team", value="Recruiter Team"),
        app_commands.Choice(name="Trainers", value="Trainers"),
        app_commands.Choice(name="Support Team", value="Support Team")
    ], status=[
        app_commands.Choice(name="Open", value="Open"),
        app_commands.Choice(name="Closed", value="Closed")
    ])
    async def setapp(self, interaction: discord.Interaction, app_type: app_commands.Choice[str], status: app_commands.Choice[str]):
        status_data = load_app_status()
        guild_id = str(interaction.guild_id)
        
        if guild_id not in status_data:
            status_data[guild_id] = {}
        
        status_data[guild_id][app_type.value] = status.value
        save_app_status(status_data)
        
        # Auto-update panel if possible
        updated = False
        config = load_panel_config()
        panel_info = config.get(guild_id)
        
        if panel_info:
            try:
                channel = interaction.guild.get_channel(panel_info["channel_id"])
                if channel:
                    message = await channel.fetch_message(panel_info["message_id"])
                    if message:
                        new_embeds = generate_panel_embeds(interaction.guild_id)
                        new_embeds[0].set_thumbnail(url=interaction.guild.icon.url if interaction.guild.icon else None)
                        await message.edit(embeds=new_embeds, view=ApplicationView())
                        updated = True
            except Exception as e:
                print(f"Failed to auto-update panel: {e}")

        msg = f"Application status for **{app_type.value}** set to **{status.value}**."
        if updated:
            msg += " The panel has been updated."
        else:
            msg += " (Could not auto-update panel. Please run /panel again if needed.)"
            
        await interaction.response.send_message(msg, ephemeral=True)

    @app_commands.command(name="setrole", description="Set the role to be given when an application is accepted")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        app_type="The type of application",
        role="The role to give"
    )
    @app_commands.choices(app_type=[
        app_commands.Choice(name="Grind Team", value="Grind Team"),
        app_commands.Choice(name="Recruiter Team", value="Recruiter Team"),
        app_commands.Choice(name="Trainers", value="Trainers"),
        app_commands.Choice(name="Support Team", value="Support Team")
    ])
    async def setrole(self, interaction: discord.Interaction, app_type: app_commands.Choice[str], role: discord.Role):
        roles_data = load_roles()
        guild_id = str(interaction.guild_id)
        
        if guild_id not in roles_data:
            roles_data[guild_id] = {}
        
        roles_data[guild_id][app_type.value] = role.id
        save_roles(roles_data)
        
        await interaction.response.send_message(f"Role for **{app_type.value}** set to {role.mention}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Applications(bot))
