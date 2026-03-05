# core/config.py
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Bot Configuration
    DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
    GUILD_ID = int(os.getenv("GUILD_ID")) if os.getenv("GUILD_ID") else None
    LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID")) if os.getenv("LOG_CHANNEL_ID") else None
    PANEL_CHANNEL_ID = int(os.getenv("PANEL_CHANNEL_ID")) if os.getenv("PANEL_CHANNEL_ID") else None

    # Database Configuration
    POSTGRES_URL = os.getenv("POSTGRES_URL")
    MONGODB_URL = os.getenv("MONGODB_URL")
    REDIS_URL = os.getenv("REDIS_URL")

    # Admin Configuration
    ADMIN_ROLE_IDS = [int(rid) for rid in os.getenv("ADMIN_ROLE_IDS", "").split(",") if rid]
    MOD_ROLE_IDS = [int(rid) for rid in os.getenv("MOD_ROLE_IDS", "").split(",") if rid]

    # Dashboard Configuration
    DASHBOARD_PORT = int(os.getenv("DASHBOARD_PORT", 3000))
    DASHBOARD_HOST = os.getenv("DASHBOARD_HOST", "0.0.0.0")
    SECRET_KEY = os.getenv("SECRET_KEY", "supersecret")

    # Game Mechanics
    BLACK_FLASH_CHANCE = 0.01
    WORLD_BOSS_MAX_ATTACKERS = 23
    RAID_MAX_PLAYERS = 12
    RAID_HP_SCALING = 0.20  # +20% HP per player
    BOSS_BUFF_RANGE = (0.07, 0.16)  # 7-16% buff logic
