import asyncio
import os
import shutil
import sys
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Union

from pyrogram import Client as BotClient, filters, raw, idle
from pyrogram.errors import ChatAdminRequired
from pyrogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery
)

from config import config
from db import db


class Client(BotClient):
    def __init__(self, session_name, api_id, api_hash, bot_token):
        super().__init__(session_name, api_id, api_hash, bot_token=bot_token)
        self.db_channel = None
        self.bot_username = None

    async def add_user_(self, m: Message):
        user_id = m.from_user.id
        if not await db.is_exist(user_id):
            await db.add_user(user_id)
            if config.log_channel:
                await self.send_message(
                    config.log_channel,
                    f"#NEW_USER\n\nNama: {m.from_user.first_name}\nId: {m.from_user.id}\nLink: {m.from_user.mention}"
                )

    async def start(self):
        await super().start()
        try:
            self.db_channel = (await self.get_chat(config.db_chid)).invite_link
        except ChatAdminRequired:
            await self.send_message(
                config.log_channel,
                "**Bot harus menjadi admin di channel database!**\n**Sistem dimatikan**"
            )
            return sys.exit()
        self.bot_username = (await self.get_me()).username

    async def stop(self, *args, **kwargs):
        return await super().stop()

    async def leave_chat(self, chat_id: Union[int, str], delete: bool = False):
        await self.send_message(
            chat_id,
            "**Maaf, chat ini ada pada list banned dan tidak bisa diakses!**",
        )
        peer = await self.resolve_peer(chat_id)

        if isinstance(peer, raw.types.InputPeerChannel):
            return await self.send(
                raw.functions.channels.LeaveChannel(
                    channel=await self.resolve_peer(chat_id)
                )
            )
        elif isinstance(peer, raw.types.InputPeerChat):
            r = await self.send(
                raw.functions.messages.DeleteChatUser(
                    chat_id=peer.chat_id,
                    user_id=raw.types.InputUserSelf()
                )
            )
            if delete:
                await self.send(
                    raw.functions.messages.DeleteHistory(
                        peer=peer,
                        max_id=0
                    )
                )
            return r


bot = Client(
    ":memory:",
    config.api_id,
    config.api_hash,
    bot_token=config.bot_token
)

DB_PATH = Path(__file__).parent / "bot.db"
BACKUP_DIR = Path(__file__).parent / config.backup_dir


def ensure_backup_dir() -> None:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)


def create_backup() -> Path:
    ensure_backup_dir()
    if not DB_PATH.exists():
        raise FileNotFoundError("Database file bot.db tidak ditemukan")
    backup_filename = f"bot_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    backup_path = BACKUP_DIR / backup_filename
    shutil.copy2(DB_PATH, backup_path)
    return backup_path


def get_backup_files() -> list[str]:
    ensure_backup_dir()
    return sorted(
        [path.name for path in BACKUP_DIR.iterdir() if path.is_file() and path.suffix == ".db"],
        reverse=True
    )


def restore_backup(filename: str) -> Path:
    backup_path = BACKUP_DIR / filename
    if not backup_path.exists() or not backup_path.is_file():
        raise FileNotFoundError(f"Backup '{filename}' tidak ditemukan")
    shutil.copy2(backup_path, DB_PATH)
    return backup_path


async def send_backup_to_log(backup_path: Path) -> None:
    if config.log_channel:
        zip_filename = f"bot_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        zip_path = BACKUP_DIR / zip_filename
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(backup_path, arcname=backup_path.name)
        
        await bot.send_document(
            config.log_channel,
            document=str(zip_path),
            caption=f"Backup database dibuat pada {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        zip_path.unlink()  # Hapus zip setelah dikirim


async def daily_backup_loop() -> None:
    while True:
        now = datetime.now()
        next_midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        await asyncio.sleep((next_midnight - now).total_seconds())
        try:
            backup_path = create_backup()
            if config.log_channel:
                await send_backup_to_log(backup_path)
        except Exception as e:
            print(f"Gagal membuat backup otomatis: {e}")


def normalize_channel_name(channel: str) -> str:
    if not channel:
        return ""
    channel = channel.strip()
    channel = channel.removeprefix("https://t.me/")
    channel = channel.removeprefix("http://t.me/")
    channel = channel.lstrip("@")
    return channel


def channel_to_peer(channel: str) -> Union[int, str]:
    if channel.startswith("-100") and channel[1:].isdigit():
        return int(channel)
    if channel.isdigit():
        return int(channel)
    return channel


def build_channel_buttons(channels: list[str]) -> InlineKeyboardMarkup:
    buttons = []
    for channel in channels:
        if not channel:
            continue
        if channel.startswith("-100") and channel[1:].isdigit():
            join_url = f"https://t.me/c/{channel[4:]}"
            label = "Gabung Group"
        elif channel.isdigit():
            join_url = f"https://t.me/c/{channel}"
            label = "Gabung Group"
        else:
            join_url = f"https://t.me/{channel}"
            label = f"Gabung @{channel}"
        buttons.append([InlineKeyboardButton(label, url=join_url)])
    return InlineKeyboardMarkup(buttons)


# Fungsi untuk memeriksa apakah user sudah bergabung ke salah satu fsub channel
async def check_fsub(client: Client, user_id: int) -> Union[bool, InlineKeyboardMarkup]:
    fsub_channels = await db.get_fsub_channels()
    if not fsub_channels:
        return True  # Tidak ada channel fsub, izinkan user lanjut

    fsub_channels = [normalize_channel_name(x) for x in fsub_channels if x and x.strip()]
    for fsub_channel in fsub_channels:
        try:
            member = await client.get_chat_member(channel_to_peer(fsub_channel), user_id)
            if member.status in ("member", "administrator", "creator"):
                return True
        except Exception:
            continue

    return build_channel_buttons(fsub_channels)


# Bot management command untuk menambahkan fsub channel secara dinamis
@bot.on_message(filters.command("addgc") & filters.private)
async def addgc_handler(c: Client, m: Message):
    if not config.owner_id:
        return await m.reply(
            "OWNER_ID belum dikonfigurasi. Tambahkan OWNER_ID di local.env atau environment variable."
        )

    if m.from_user.id not in config.owner_id:
        return await m.reply("Hanya owner bot yang dapat menggunakan perintah ini.")

    args = m.text.split(None, 1)
    if len(args) < 2 or not args[1].strip():
        return await m.reply(
            "Gunakan: /addgc <username atau id grup/channel>\nContoh: /addgc BestieVirtual atau /addgc -1001234567890"
        )

    channel = normalize_channel_name(args[1])
    if not channel:
        return await m.reply("ID atau username channel tidak valid.")

    if await db.is_fsub_channel(channel):
        return await m.reply(f"Channel {channel} sudah terdaftar sebagai fsub.")

    await db.add_fsub_channel(channel)
    return await m.reply(f"Berhasil menambahkan channel fsub: {channel}")


@bot.on_message(filters.command("listgc") & filters.private)
async def listgc_handler(c: Client, m: Message):
    if not config.owner_id:
        return await m.reply(
            "OWNER_ID belum dikonfigurasi. Tambahkan OWNER_ID di local.env atau environment variable."
        )

    if m.from_user.id not in config.owner_id:
        return await m.reply("Hanya owner bot yang dapat menggunakan perintah ini.")

    fsub_channels = await db.get_fsub_channels()
    if not fsub_channels:
        return await m.reply("Belum ada channel fsub yang tersimpan.")

    channel_list = "\n".join(f"- {channel}" for channel in fsub_channels)
    return await m.reply(f"Daftar channel fsub saat ini:\n{channel_list}")


@bot.on_message(filters.command("backup") & filters.private)
async def backup_handler(c: Client, m: Message):
    if not config.owner_id:
        return await m.reply(
            "OWNER_ID belum dikonfigurasi. Tambahkan OWNER_ID di local.env atau environment variable."
        )

    if m.from_user.id not in config.owner_id:
        return await m.reply("Hanya owner bot yang dapat menggunakan perintah ini.")

    try:
        status_msg = await m.reply("⏳ Membuat backup...")
        backup_path = create_backup()
        await status_msg.delete()
        
        await m.reply_document(
            document=str(backup_path),
            caption=f"✅ Backup berhasil dibuat: {backup_path.name}"
        )
        
        if config.log_channel:
            await bot.send_document(
                config.log_channel,
                document=str(backup_path),
                caption=f"Backup dibuat oleh owner pada {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
    except Exception as e:
        return await m.reply(f"❌ Gagal membuat backup: {e}")


@bot.on_message(filters.command("listbackup") & filters.private)
async def listbackup_handler(c: Client, m: Message):
    if not config.owner_id:
        return await m.reply(
            "OWNER_ID belum dikonfigurasi. Tambahkan OWNER_ID di local.env atau environment variable."
        )

    if m.from_user.id not in config.owner_id:
        return await m.reply("Hanya owner bot yang dapat menggunakan perintah ini.")

    backup_files = get_backup_files()
    if not backup_files:
        return await m.reply("Belum ada file backup.")

    file_list = "\n".join(f"- {name}" for name in backup_files)
    return await m.reply(f"Daftar backup yang tersedia:\n{file_list}")


@bot.on_message(filters.command("restore") & filters.private)
async def restore_handler(c: Client, m: Message):
    if not config.owner_id:
        return await m.reply(
            "OWNER_ID belum dikonfigurasi. Tambahkan OWNER_ID di local.env atau environment variable."
        )

    if m.from_user.id not in config.owner_id:
        return await m.reply("Hanya owner bot yang dapat menggunakan perintah ini.")

    backup_to_restore = None
    backup_file_path = None

    if m.reply_to_message and m.reply_to_message.document:
        try:
            status_msg = await m.reply("⏳ Mengunduh file backup...")
            file_path = await m.reply_to_message.download()
            backup_file_path = file_path
            await status_msg.delete()
        except Exception as e:
            return await m.reply(f"❌ Gagal mengunduh file: {e}")
    else:
        args = m.text.split(None, 1)
        if len(args) < 2 or not args[1].strip():
            return await m.reply(
                "Cara pakai:\n"
                "1️⃣ /restore <nama_backup.db> (dari folder backup)"
                "   Contoh: /restore bot_backup_20240503_000000.db\n"
                "2️⃣ /restore latest (backup terbaru)"
                "   Contoh: /restore latest\n"
                "3️⃣ Reply pesan dengan file .db, lalu /restore"
            )

        backup_name = args[1].strip()
        if backup_name == "latest":
            backup_files = get_backup_files()
            if not backup_files:
                return await m.reply("Belum ada file backup untuk di-restore.")
            backup_name = backup_files[0]

        backup_path = BACKUP_DIR / backup_name
        if not backup_path.exists() or not backup_path.is_file():
            return await m.reply(f"❌ Backup '{backup_name}' tidak ditemukan")
        
        backup_file_path = backup_path

    try:
        status_msg = await m.reply("⏳ Restore database...")
        await db.disconnect()
        shutil.copy2(backup_file_path, DB_PATH)
        await db.connect()
        await db.init()
        await status_msg.delete()
        await m.reply("✅ Restore berhasil! Bot perlu di-restart untuk hasil optimal.")
        
        if config.log_channel:
            await bot.send_message(
                config.log_channel,
                f"🔄 Restore database dilakukan oleh owner\nWaktu: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
    except Exception as e:
        await m.reply(f"❌ Gagal restore: {e}")
        try:
            await db.connect()
            await db.init()
        except:
            pass


# Handler Start
@bot.on_message(filters.command("start") & filters.private)
async def start_hndlr(c: Client, m: Message):
    if m.from_user.id in await db.get_all_banned_user():
        return await m.reply("Maaf, anda terban oleh owner kami.")

    await c.add_user_(m)
    check = await check_fsub(c, m.from_user.id)
    if check is not True:
        return await m.reply(
            "**Silakan gabung ke channel kami dulu sebelum lanjut.**",
            reply_markup=check
        )

    return await m.reply(
        "Hi, silakan kirim pesan atau gambar yang ingin kamu kirim secara anonim.",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("About Bot", "aboutbot"),
                    InlineKeyboardButton("About Dev", "aboutdev")
                ]
            ]
        )
    )


# Handler pesan teks/media
@bot.on_message((filters.text | filters.media) & ~filters.sticker)
async def send_media_(c: Client, m: Message):
    if m.chat.type != "private":
        return

    await c.add_user_(m)
    check = await check_fsub(c, m.from_user.id)
    if check is not True:
        return await m.reply(
            "**Silakan gabung ke channel kami dulu sebelum lanjut.**",
            reply_markup=check
        )

    # Ambil daftar channel dari database
    channels = await db.get_fsub_channels()
    if not channels:
        return await m.reply("Maaf, tidak ada channel tujuan yang tersedia saat ini.")

    # Buat tombol dinamis dari channel yang ada
    buttons = []
    for idx, channel in enumerate(channels, 1):
        buttons.append([InlineKeyboardButton(f"Channel {idx}", callback_data=f"send_channel_{idx}")])
    
    return await m.reply(
        f"**Mau kirim {'media' if not m.text else 'pesan'} kemana?**",
        reply_markup=InlineKeyboardMarkup(buttons),
        quote=True
    )


# Callback handler kirim ke channel
@bot.on_callback_query(filters.regex(r"send_channel_(\d+)"))
async def send_channel_handler(c: Client, cb: CallbackQuery):
    m = cb.message
    if not m.reply_to_message:
        return await cb.answer("Pesan tidak ditemukan", show_alert=True)
    
    try:
        channel_idx = int(cb.matches[0].group(1)) - 1
        channels = await db.get_fsub_channels()
        
        if channel_idx >= len(channels):
            return await cb.answer("Channel tidak valid", show_alert=True)
        
        channel_tujuan = normalize_channel_name(channels[channel_idx])
        channel_peer = channel_to_peer(channel_tujuan)
        message_id = m.reply_to_message.message_id
        
        x = await c.copy_message(
            channel_peer,
            m.chat.id,
            message_id,
            caption=m.caption or None
        )
        
        await m.delete()
        await m.reply(
            "**Pesan berhasil terkirim, silakan lihat dengan klik tombol dibawah ini!**",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("Klik disini", url=f"https://t.me/c/{str(x.chat.id)[4:]}/{x.message_id}")
            ]])
        )
        
        fwd = await c.forward_messages(
            config.log_channel,
            m.chat.id,
            message_id
        )
        
        reply_msg = m.reply_to_message
        await fwd.reply(
            (
                "**User mengirim pesan**\n"
                f"Nama: {reply_msg.from_user.first_name}\n"
                f"Id: {reply_msg.from_user.id}\n"
                f"Username: {reply_msg.from_user.mention}\n"
                f"Channel tujuan: {channels[channel_idx]}"
            )
        )
    except Exception as e:
        await cb.answer(f"Error: {e}", show_alert=True)


# Main loop
async def main():
    try:
        await db.connect()
        await db.init()
        print(f"[{datetime.now()}] Berjalan")
        await asyncio.sleep(1)
        await bot.start()
        asyncio.create_task(daily_backup_loop())
        await idle()
        await bot.stop()
    except KeyboardInterrupt:
        return sys.exit()


asyncio.get_event_loop().run_until_complete(main())
