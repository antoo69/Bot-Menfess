from dotenv import load_dotenv
from os import getenv, path

load_dotenv() if not path.exists("local.env") else load_dotenv("local.env")


class Config:
    api_id = int(getenv("API_ID", "23345148"))
    api_hash = getenv("API_HASH", "fe37a47fef4345512ed47c17d3306f0b")
    bot_token = getenv("BOT_TOKEN", "8161422676:AAGnGOJ8nn-_HftdLZJ6gWqmY2xbfnJ43Bw")
    fsub_channel = getenv("FSUB_CHANNEL", "BestieVirtual")
    fsub_channel2 = getenv("FSUB_CHANNEL2", "BestieVirtualPap")  # Channel kedua
    fsub_channel3 = getenv("FSUB_CHANNEL3")
    log_channel = int(getenv("LOG_CHANNEL", "-1002351111178"))
    db_chid = int(getenv("DB_CHANNEL", "-1002351111178"))
    blacklisted_channel = [int(x) for x in getenv("BLACKLISTED_CHANNEL", "123").split(",") if x is not None]
    channel1 = int(getenv("CHANNEL_1", "-1002280848465"))
    channel2 = int(getenv("CHANNEL_2", "-1002079962899"))
    channel3 = int(getenv("CHANNEL_3", "-1002348472641"))


config = Config()
