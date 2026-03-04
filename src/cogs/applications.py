import discord
from discord import app_commands, ui
from discord.ext import commands
import os

# --- Constants ---
LOG_CHANNEL_ID = os.getenv('LOG_CHANNEL_ID')

# --- Modals ---

class GrindTeamModal(ui.Modal, title='Grind Team Application'):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    level_progression = ui.TextInput(
        label='Current Level / Progression',
        style=discord.TextStyle.short,
        placeholder='e.g., Lvl 50, just started late game...',
        required=True,
        max_length=100
    )
    
    game_knowledge = ui.TextInput(
        label='Game Knowledge & Excel Areas',
        style=discord.TextStyle.long,
        placeholder='Describe your game sense and what you are good at...',
        required=True,
        max_length=500
    )

    helping_experience = ui.TextInput(
        label='Experience Helping Others',
        style=discord.TextStyle.paragraph,
        placeholder='Have you guided others before? Describe...',
        required=True,
        max_length=500
    )

    availability = ui.TextInput(
        label='Weekly Availability (Hours)',
        style=discord.TextStyle.short,
        placeholder='e.g., 10-15 hours/week',
        required=True,
        max_length=100
    )

    why_fit = ui.TextInput(
        label='Why are you a good fit?',
        style=discord.TextStyle.paragraph,
        placeholder='What makes you suitable for the Grind Team?',
        required=True,
        max_length=500
    )

    async def on_submit(self, interaction: discord.Interaction):
        await send_application_log(self.bot, interaction, "Grind Team", [
            ("Current Level / Progression", self.level_progression.value),
            ("Game Knowledge", self.game_knowledge.value),
            ("Helping Experience", self.helping_experience.value),
            ("Availability", self.availability.value),
            ("Why Fit", self.why_fit.value)
        ])

class RecruiterTeamModal(ui.Modal, title='Recruiter Team Application'):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    motivation = ui.TextInput(
        label='Why do you want to be a recruiter?',
        style=discord.TextStyle.paragraph,
        required=True
    )

    invites_count = ui.TextInput(
        label='How many invites do you have?',
        placeholder='10 invites required',
        style=discord.TextStyle.short,
        required=True
    )

    pitch = ui.TextInput(
        label='How would you pitch Kamu?',
        style=discord.TextStyle.paragraph,
        placeholder='Pitch to someone who never heard of it...',
        required=True
    )

    methods = ui.TextInput(
        label='Recruiting Methods',
        style=discord.TextStyle.paragraph,
        placeholder='What methods would you use?',
        required=True
    )

    experience_activity = ui.TextInput(
        label='Experience & Expected Activity',
        style=discord.TextStyle.paragraph,
        placeholder='Previous exp? How active will you be?',
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        await send_application_log(self.bot, interaction, "Recruiter Team", [
            ("Motivation", self.motivation.value),
            ("Invites Count", self.invites_count.value),
            ("Pitch", self.pitch.value),
            ("Methods", self.methods.value),
            ("Experience & Activity", self.experience_activity.value)
        ])

class SupportTeamModal(ui.Modal, title='Support Team Application'):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    familiarity = ui.TextInput(
        label='Familiarity with Server',
        style=discord.TextStyle.paragraph,
        placeholder='Layout, channels, structure...',
        required=True
    )

    handling_confusion = ui.TextInput(
        label='Handling Confused Members',
        style=discord.TextStyle.paragraph,
        placeholder='How would you handle frustration?',
        required=True
    )

    experience = ui.TextInput(
        label='Assistance Experience',
        style=discord.TextStyle.paragraph,
        placeholder='Have you assisted in other servers?',
        required=True
    )

    comm_style = ui.TextInput(
        label='Communication Style',
        style=discord.TextStyle.short,
        placeholder='Describe your style...',
        required=True
    )

    activity_promo = ui.TextInput(
        label='Activity & Promotion Ideas',
        style=discord.TextStyle.paragraph,
        placeholder='Activity level? Ideas to promote/explain Kamu?',
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        await send_application_log(self.bot, interaction, "Support Team", [
            ("Familiarity", self.familiarity.value),
            ("Handling Confusion", self.handling_confusion.value),
            ("Experience", self.experience.value),
            ("Communication Style", self.comm_style.value),
            ("Activity & Promotion", self.activity_promo.value)
        ])

class TrainersModalPart2(ui.Modal, title='Trainers App (Part 2/2)'):
    def __init__(self, bot, part1_data):
        super().__init__()
        self.bot = bot
        self.part1_data = part1_data

    organized_engaging = ui.TextInput(
        label='Keeping Events Organized',
        style=discord.TextStyle.paragraph,
        placeholder='How to keep it engaging?',
        required=True
    )

    disruptive_handling = ui.TextInput(
        label='Handling Disruptive Players',
        style=discord.TextStyle.paragraph,
        placeholder='What if it becomes chaotic?',
        required=True
    )

    experience = ui.TextInput(
        label='Previous Experience',
        style=discord.TextStyle.paragraph,
        placeholder='State your experience...',
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        # Combine data
        full_data = self.part1_data + [
            ("Organized & Engaging", self.organized_engaging.value),
            ("Disruptive Handling", self.disruptive_handling.value),
            ("Experience", self.experience.value)
        ]
        
        await send_application_log(self.bot, interaction, "Trainers", full_data)

class ContinueTrainersView(ui.View):
    def __init__(self, bot, part1_data):
        super().__init__(timeout=600)
        self.bot = bot
        self.part1_data = part1_data

    @ui.button(label="Continue to Part 2", style=discord.ButtonStyle.primary)
    async def continue_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(TrainersModalPart2(self.bot, self.part1_data))

class TrainersModalPart1(ui.Modal, title='Trainers App (Part 1/2)'):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    motivation = ui.TextInput(
        label='Why Trainer / Suitability',
        style=discord.TextStyle.paragraph,
        required=True
    )

    activity = ui.TextInput(
        label='Activity (1-10) & Hosting Freq',
        style=discord.TextStyle.short,
        placeholder='Rate 1-10. How often can you host?',
        required=True
    )

    fair_ranking = ui.TextInput(
        label='Ensuring Fair Ranking',
        style=discord.TextStyle.paragraph,
        required=True
    )

    disagreement = ui.TextInput(
        label='Handling Rank Disagreements',
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
            view=ContinueTrainersView(self.bot, part1_data),
            ephemeral=True
        )

# --- Helper Functions ---

async def send_application_log(bot, interaction: discord.Interaction, app_type: str, fields: list):
    embed = discord.Embed(
        title=f"New {app_type} Application",
        color=discord.Color.blue(),
        timestamp=interaction.created_at
    )
    embed.set_author(name=f"{interaction.user.name} ({interaction.user.id})", icon_url=interaction.user.display_avatar.url)
    
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
        await log_channel.send(embed=embed)
        await interaction.response.send_message("Application submitted successfully!", ephemeral=True)
    else:
        await interaction.response.send_message("Application submitted! (Note: 'application-logs' channel not found, so admins might not see this immediately.)", ephemeral=True)


# --- Views ---

class ApplicationSelect(ui.Select):
    def __init__(self, bot):
        self.bot = bot
        options = [
            discord.SelectOption(label="Grind Team App", description="Apply for the Grind Team", emoji="⚔️"),
            discord.SelectOption(label="Recruiter App", description="Apply for the Recruiter Team", emoji="📢"),
            discord.SelectOption(label="Trainers App", description="Apply to become a Trainer", emoji="🎓"),
            discord.SelectOption(label="Support Team App", description="Apply for the Support Team", emoji="🛡️"),
        ]
        super().__init__(placeholder="Select an application...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        choice = self.values[0]
        
        if choice == "Grind Team App":
            await interaction.response.send_modal(GrindTeamModal(self.bot))
        elif choice == "Recruiter App":
            await interaction.response.send_modal(RecruiterTeamModal(self.bot))
        elif choice == "Trainers App":
            await interaction.response.send_modal(TrainersModalPart1(self.bot))
        elif choice == "Support Team App":
            await interaction.response.send_modal(SupportTeamModal(self.bot))

class ApplicationView(ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None) # Persistent view
        self.add_item(ApplicationSelect(bot))

# --- Cog ---

class Applications(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        self.bot.add_view(ApplicationView(self.bot))

    @app_commands.command(name="panel", description="Creates the application panel")
    @app_commands.checks.has_permissions(administrator=True)
    async def panel(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="Kamu Guild Applications",
            description="Please select the team you wish to apply for from the dropdown below.",
            color=discord.Color.gold()
        )
        embed.set_footer(text="Kamu Guild • Kaizen")
        embed.set_thumbnail(url=interaction.guild.icon.url if interaction.guild.icon else None)
        
        await interaction.response.send_message(embed=embed, view=ApplicationView(self.bot))

async def setup(bot):
    await bot.add_cog(Applications(bot))
