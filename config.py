from dotenv import load_dotenv
from os import getenv, path

load_dotenv() if not path.exists("local.env") else load_dotenv("local.env")


def _get_int(name: str, default: str = "0") -> int | None:
    value = getenv(name, default).strip()
    if not value:
        return None
    return int(value)


def _get_int_list(name: str, default: str = "") -> list[int]:
    values = []
    for raw in getenv(name, default).split(","):
        item = raw.strip()
        if item and item.lstrip("-").isdigit():
            values.append(int(item))
    return values


class Config:
    api_id = _get_int("API_ID, 39539870")
    api_hash = getenv("API_HASH", "655c51c79a9c59192dc95baaa72bb99d").strip()
    bot_token = getenv("BOT_TOKEN", "8718028794:AAESRyihzAAqnIJaNk8eRmjg12brq9p0CaE").strip()
    log_channel = _get_int("LOG_CHANNEL, -1002356369190")
    db_chid = _get_int("DB_CHANNEL, -1002356369190")
    blacklisted_channel = _get_int_list("BLACKLISTED_CHANNEL")
    owner_id = _get_int_list("OWNER_ID, 1086812385")
    dev_id = _get_int_list("DEV_ID, 1086812385")
    backup_dir = getenv("BACKUP_DIR", "backups")

    @classmethod
    def missing_required(cls) -> list[str]:
        missing = []
        if not cls.api_id:
            missing.append("API_ID")
        if not cls.api_hash:
            missing.append("API_HASH")
        if not cls.bot_token:
            missing.append("BOT_TOKEN")
        if not cls.db_chid:
            missing.append("DB_CHANNEL")
        if not cls.dev_id:
            missing.append("DEV_ID")
        return missing


config = Config()
