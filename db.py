from databases import Database
from datetime import datetime


class DB:
    def __init__(self):
        self.db = Database("sqlite+aiosqlite:///bot.db")

    async def connect(self):
        return await self.db.connect()

    async def disconnect(self):
        return await self.db.disconnect()

    async def init(self):
        await self.db.execute(
            """
            create table if not exists user_db
            (
                user_id integer,
                is_banned boolean,
                ban_duration integer,
                ban_reason text
            )
            """
        )
        await self.db.execute(
            """
            create table if not exists fsub_channel
            (
                channel text primary key
            )
            """
        )
        await self.db.execute(
            """
            create table if not exists bot_settings
            (
                key text primary key,
                value text
            )
            """
        )
        await self.ensure_default_settings()
        return

    async def ensure_default_settings(self):
        defaults = {
            "is_active": "0",
            "expires_at": "",
            "fsub_limit": "0",
            "group_limit": "0",
            "content_limit": "0",
        }
        for key, value in defaults.items():
            await self.db.execute(
                """
                insert or ignore into bot_settings(key, value)
                values (:key, :value)
                """,
                {"key": key, "value": value}
            )

    async def add_user(self, user_id: int):
        is_exists = await self.is_exist(user_id)
        if not is_exists:
            data = {
                "user_id": user_id,
                "is_banned": False,
                "ban_duration": 0,
                "ban_reason": ""
            }
            return await self.db.execute("insert into user_db values (:user_id, :is_banned, :ban_duration, :ban_reason)", data)

    async def is_exist(self, user_id: int):
        data = await self.db.fetch_one("select * from user_db where user_id = :user_id", {"user_id": user_id})
        return bool(data)

    async def get_total_users(self):
        count = list(await self.db.fetch_all("select * from user_db"))
        return len(count)

    async def get_all_users(self):
        all_user = await self.db.fetch_all("select user_id from user_db")
        return all_user

    async def add_fsub_channel(self, channel: str):
        if not await self.is_fsub_channel(channel):
            return await self.db.execute(
                "insert into fsub_channel values (:channel)",
                {"channel": channel}
            )

    async def is_fsub_channel(self, channel: str):
        data = await self.db.fetch_one(
            "select channel from fsub_channel where channel = :channel",
            {"channel": channel}
        )
        return bool(data)

    async def get_fsub_channels(self):
        rows = await self.db.fetch_all("select channel from fsub_channel")
        return [row[0] for row in rows]

    async def get_fsub_channel_count(self):
        row = await self.db.fetch_one("select count(*) from fsub_channel")
        return int(row[0]) if row else 0

    async def del_fsub_channel(self, channel: str):
        return await self.db.execute(
            "delete from fsub_channel where channel = :channel",
            {"channel": channel}
        )

    async def del_user(self, user_id: int):
        return await self.db.execute("delete from user_db where user_id = :user_id", {"user_id": user_id})

    async def del_ban(self, user_id: int):
        data = {
            "is_banned": False,
            "ban_duration": 0,
            "ban_reason": "",
            "user_id": user_id,
        }
        await self.db.execute(
            """
            update user_db
            set is_banned = :is_banned,
                ban_duration = :ban_duration,
                ban_reason = :ban_reason
            where user_id = :user_id
            """,
            data
        )

    async def ban(self, user_id: int, ban_duration: int, ban_reason: str):
        is_banned = await self.db.fetch_one("select is_banned from user_db where user_id = :user_id", {"user_id": user_id})
        is_exists = await self.db.fetch_one("select user_id from user_db where user_id = :user_id", {"user_id": user_id})
        is_exists = is_exists[0] if is_exists else is_exists
        is_banned = is_banned[0] if is_banned else is_banned
        if is_exists and not is_banned:
            data = dict(
                is_banned=True,
                ban_duration=ban_duration,
                ban_reason=ban_reason,
                user_id=user_id,
            )
            await self.db.execute(
                """
                update user_db
                set is_banned = :is_banned,
                    ban_duration = :ban_duration,
                    ban_reason = :ban_reason
                where user_id = :user_id
                """,
                data
            )
        elif not is_exists and not is_banned:
            await self.db.execute(
                """
                insert into user_db
                values (
                    :user_id,
                    :is_banned,
                    :ban_duration,
                    :ban_reason
                )
                """,
                {
                    "user_id": user_id,
                    "is_banned": True,
                    "ban_duration": ban_duration,
                    "ban_reason": ban_reason
                }
            )

    async def get_ban_status(self, user_id: int):
        user = await self.db.fetch_one("select * from user_db where user_id = :user_id", {"user_id": user_id})
        if not user:
            return False
        _, is_banned, _, _ = user
        return bool(is_banned)

    async def get_all_banned_user(self):
        users = await self.db.fetch_all("select user_id from user_db where is_banned = :is_banned", {"is_banned": True})
        return [user[0] for user in users]

    async def set_setting(self, key: str, value: str):
        await self.db.execute(
            """
            insert into bot_settings(key, value)
            values (:key, :value)
            on conflict(key) do update set value = excluded.value
            """,
            {"key": key, "value": value}
        )

    async def get_setting(self, key: str, default: str = ""):
        row = await self.db.fetch_one(
            "select value from bot_settings where key = :key",
            {"key": key}
        )
        return row[0] if row else default

    async def get_bot_settings(self):
        rows = await self.db.fetch_all("select key, value from bot_settings")
        data = {row[0]: row[1] for row in rows}
        expires_at_raw = data.get("expires_at", "")
        expires_at = None
        if expires_at_raw:
            try:
                expires_at = datetime.fromisoformat(expires_at_raw)
            except ValueError:
                expires_at = None

        return {
            "is_active": data.get("is_active", "0") == "1",
            "expires_at": expires_at,
            "fsub_limit": int(data.get("fsub_limit", "0") or 0),
            "group_limit": int(data.get("group_limit", "0") or 0),
            "content_limit": int(data.get("content_limit", "0") or 0),
        }


db = DB()
