import discord
from discord.ext import commands
import sqlite3
import os

DB_FILE = 'moderation.db'
ADMIN_ID = 1313484931892117524

class ModerationCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.init_db()

    def init_db(self):
        with sqlite3.connect(DB_FILE) as conn:
            c = conn.cursor()
            c.execute('''CREATE TABLE IF NOT EXISTS user_ips
                         (user_id INTEGER, ip_address TEXT, 
                          PRIMARY KEY (user_id, ip_address))''')
            conn.commit()

    def is_admin(self, ctx):
        return ctx.author.id == ADMIN_ID

    @commands.command(name="ipadd")
    async def add_ip_command(self, ctx, user: discord.User, ip: str):
        """Manually associate an IP with a user (Admin only)."""
        if not self.is_admin(ctx):
            await ctx.send("You do not have permission to use this command.")
            return

        with sqlite3.connect(DB_FILE) as conn:
            c = conn.cursor()
            c.execute("INSERT OR IGNORE INTO user_ips (user_id, ip_address) VALUES (?, ?)", (user.id, ip))
            conn.commit()
        
        await ctx.send(f"Associated IP `{ip}` with user {user.mention} (`{user.id}`).")

    @commands.command(name="ipshow")
    async def ip_show_command(self, ctx, user: discord.User):
        """Shows users associated with the same IP addresses as the target user."""
        if not self.is_admin(ctx):
            await ctx.send("You do not have permission to use this command.")
            return

        with sqlite3.connect(DB_FILE) as conn:
            c = conn.cursor()
            
            # 1. Get IPs for the target user
            c.execute("SELECT ip_address FROM user_ips WHERE user_id = ?", (user.id,))
            ips = [row[0] for row in c.fetchall()]

            if not ips:
                await ctx.send(f"No IP addresses recorded for {user.mention}.")
                return

            embed = discord.Embed(title=f"IP Report for {user.display_name}", color=discord.Color.red())
            
            for ip in ips:
                # 2. Get all users with this IP
                c.execute("SELECT user_id FROM user_ips WHERE ip_address = ?", (ip,))
                user_ids = [row[0] for row in c.fetchall()]
                
                # Format user list
                user_list = []
                for uid in user_ids:
                    # Try to get member from guild, fallback to ID
                    member = ctx.guild.get_member(uid)
                    if member:
                        user_list.append(f"{member.mention} (`{uid}`)")
                    else:
                        user_list.append(f"<@{uid}> (`{uid}`)")
                
                embed.add_field(name=f"IP: {ip}", value="\n".join(user_list), inline=False)

            await ctx.send(embed=embed)

    @commands.command(name="ipban")
    async def ip_ban_command(self, ctx, user: discord.User, *, reason: str = "IP Ban"):
        """Bans the user and all other users sharing the same IP addresses."""
        if not self.is_admin(ctx):
            await ctx.send("You do not have permission to use this command.")
            return

        with sqlite3.connect(DB_FILE) as conn:
            c = conn.cursor()
            
            # 1. Get IPs for the target user
            c.execute("SELECT ip_address FROM user_ips WHERE user_id = ?", (user.id,))
            ips = [row[0] for row in c.fetchall()]

            users_to_ban = set()
            users_to_ban.add(user.id)

            if ips:
                # 2. Get all users with these IPs
                placeholders = ','.join('?' for _ in ips)
                c.execute(f"SELECT user_id FROM user_ips WHERE ip_address IN ({placeholders})", ips)
                for row in c.fetchall():
                    users_to_ban.add(row[0])

        # 3. Execute Bans
        banned_users = []
        failed_users = []

        for uid in users_to_ban:
            try:
                # Need to fetch the user object to ban them
                # If they are in the guild:
                member = ctx.guild.get_member(uid)
                if member:
                    await member.ban(reason=f"{reason} (Linked to {user.display_name})")
                    banned_users.append(f"{member.display_name} (`{uid}`)")
                else:
                    # If not in guild, we can hack a ban using discord.Object
                    # But discord.py allows banning via ID if we fetch the user or use Object
                    await ctx.guild.ban(discord.Object(id=uid), reason=f"{reason} (Linked to {user.display_name})")
                    banned_users.append(f"User ID `{uid}`")
            except Exception as e:
                failed_users.append(f"ID `{uid}`: {e}")

        # 4. Report
        embed = discord.Embed(title="IP Ban Execution", color=discord.Color.dark_red())
        embed.add_field(name="Target", value=f"{user.mention} (`{user.id}`)", inline=False)
        
        if ips:
            embed.add_field(name="Linked IPs", value="\n".join(ips), inline=False)
        else:
            embed.add_field(name="Linked IPs", value="None found (Banning target only)", inline=False)

        if banned_users:
            embed.add_field(name="Banned Users", value="\n".join(banned_users), inline=False)
        
        if failed_users:
            embed.add_field(name="Failed to Ban", value="\n".join(failed_users), inline=False)

        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(ModerationCog(bot))
