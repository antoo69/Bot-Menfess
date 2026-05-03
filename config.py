from dotenv import load_dotenv
from os import getenv, path

load_dotenv() if not path.exists("local.env") else load_dotenv("local.env")


class Config:
    api_id = int(getenv("API_ID", "23345148"))
    api_hash = getenv("API_HASH", "fe37a47fef4345512ed47c17d3306f0b")
    bot_token = getenv("BOT_TOKEN", "8161422676:AAGnGOJ8nn-_HftdLZJ6gWqmY2xbfnJ43Bw")
    log_channel = int(getenv("LOG_CHANNEL", "-1002351111178"))
    db_chid = int(getenv("DB_CHANNEL", "-1002351111178"))
    blacklisted_channel = [int(x) for x in getenv("BLACKLISTED_CHANNEL", "123").split(",") if x is not None]
    owner_id = [int(x) for x in getenv("OWNER_ID", "0").split(",") if x.strip().isdigit()]
    backup_dir = getenv("BACKUP_DIR", "backups")


config = Config()
