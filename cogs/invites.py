import discord
from discord.ext import commands
import sqlite3
import datetime

DB_FILE = 'invites.db'

class InvitesCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.invites_cache = {} # {guild_id: {code: usage_count}}
        self.init_db()

    def init_db(self):
        with sqlite3.connect(DB_FILE) as conn:
            c = conn.cursor()
            c.execute('''CREATE TABLE IF NOT EXISTS invite_tracking
                         (guild_id INTEGER, inviter_id INTEGER, invitee_id INTEGER, timestamp TEXT,
                          PRIMARY KEY (guild_id, invitee_id))''')
            conn.commit()

    async def cog_load(self):
        await self.bot.wait_until_ready()
        for guild in self.bot.guilds:
            try:
                self.invites_cache[guild.id] = {}
                invites = await guild.invites()
                for invite in invites:
                    self.invites_cache[guild.id][invite.code] = invite.uses
            except discord.Forbidden:
                print(f"Missing permissions to fetch invites for guild: {guild.name} ({guild.id})")
            except Exception as e:
                print(f"Error fetching invites for guild {guild.name}: {e}")

    @commands.Cog.listener()
    async def on_invite_create(self, invite):
        if invite.guild.id not in self.invites_cache:
            self.invites_cache[invite.guild.id] = {}
        self.invites_cache[invite.guild.id][invite.code] = invite.uses

    @commands.Cog.listener()
    async def on_invite_delete(self, invite):
        if invite.guild.id in self.invites_cache and invite.code in self.invites_cache[invite.guild.id]:
            del self.invites_cache[invite.guild.id][invite.code]

    @commands.Cog.listener()
    async def on_member_join(self, member):
        guild = member.guild
        if guild.id not in self.invites_cache:
            # Try to populate cache if missing
            try:
                self.invites_cache[guild.id] = {}
                invites = await guild.invites()
                for invite in invites:
                    self.invites_cache[guild.id][invite.code] = invite.uses
            except:
                return

        try:
            current_invites = await guild.invites()
        except discord.Forbidden:
            return

        used_invite = None
        # Find the invite that has incremented uses
        for invite in current_invites:
            cached_uses = self.invites_cache[guild.id].get(invite.code, 0)
            if invite.uses > cached_uses:
                used_invite = invite
                break
        
        # Update cache with current state
        for invite in current_invites:
            self.invites_cache[guild.id][invite.code] = invite.uses

        if used_invite:
            inviter = used_invite.inviter
            if inviter:
                with sqlite3.connect(DB_FILE) as conn:
                    c = conn.cursor()
                    c.execute("INSERT OR REPLACE INTO invite_tracking (guild_id, inviter_id, invitee_id, timestamp) VALUES (?, ?, ?, ?)",
                              (guild.id, inviter.id, member.id, datetime.datetime.now(datetime.timezone.utc).isoformat()))
                    conn.commit()
                print(f"Tracked invite: {inviter} invited {member}")

    @commands.command(name="userinviteinfo")
    async def user_invite_info(self, ctx, user_id: str = None):
        if not ctx.guild:
            await ctx.send("This command can only be used in a server.")
            return

        if user_id is None:
            target_id = ctx.author.id
        else:
            # Handle user_id being a mention or just an ID
            try:
                target_id = int(user_id.strip('<@!>'))
            except ValueError:
                await ctx.send("Invalid User ID format.")
                return

        with sqlite3.connect(DB_FILE) as conn:
            c = conn.cursor()
            c.execute("SELECT invitee_id, timestamp FROM invite_tracking WHERE guild_id = ? AND inviter_id = ?", (ctx.guild.id, target_id))
            rows = c.fetchall()

        if not rows:
            msg = f"<@{target_id}> has not invited anyone (that I've tracked)." if user_id else "You have not invited anyone (that I've tracked)."
            await ctx.send(msg)
            return

        # Fetch member objects to display names if possible, otherwise IDs
        invited_list = []
        for row in rows:
            invitee_id, timestamp = row
            # Try to format timestamp nicely
            try:
                dt = datetime.datetime.fromisoformat(timestamp)
                ts_str = dt.strftime("%Y-%m-%d %H:%M UTC")
            except:
                ts_str = timestamp
            
            invited_list.append(f"• <@{invitee_id}> (ID: {invitee_id}) - Joined: {ts_str}")

        # Create embed
        embed = discord.Embed(title=f"Invites by {target_id}", color=discord.Color.blue())
        
        # Chunking for embed fields (max 1024 chars per field)
        current_chunk = ""
        field_count = 1
        
        for line in invited_list:
            if len(current_chunk) + len(line) + 1 > 1000:
                embed.add_field(name=f"Invited Users (Part {field_count})", value=current_chunk, inline=False)
                current_chunk = line + "\n"
                field_count += 1
            else:
                current_chunk += line + "\n"
        
        if current_chunk:
            embed.add_field(name=f"Invited Users (Part {field_count})", value=current_chunk, inline=False)

        embed.set_footer(text=f"Total Invites: {len(rows)}")
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(InvitesCog(bot))
