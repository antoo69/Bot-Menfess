import asyncio
import math
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
                await safe_send_message(
                    config.log_channel,
                    f"#NEW_USER\n\nNama: {m.from_user.first_name}\nId: {m.from_user.id}\nLink: {m.from_user.mention}"
                )

    async def start(self):
        await super().start()
        try:
            self.db_channel = (await self.get_chat(config.db_chid)).invite_link
        except ChatAdminRequired:
            await safe_send_message(
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
        
        await safe_send_document(
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


def build_message_link(chat, message_id: int) -> str | None:
    if getattr(chat, "username", None):
        return f"https://t.me/{chat.username}/{message_id}"

    chat_id = str(chat.id)
    if chat_id.startswith("-100"):
        return f"https://t.me/c/{chat_id[4:]}/{message_id}"

    return None


async def safe_send_message(chat_id: int | None, text: str) -> None:
    if not chat_id:
        return
    try:
        await bot.send_message(chat_id, text)
    except Exception as exc:
        print(f"Gagal kirim log message: {exc}")


async def safe_send_document(chat_id: int | None, document: str, caption: str) -> None:
    if not chat_id:
        return
    try:
        await bot.send_document(chat_id, document=document, caption=caption)
    except Exception as exc:
        print(f"Gagal kirim log document: {exc}")


def format_expiry(expires_at: datetime | None) -> str:
    if not expires_at:
        return "Belum diatur"
    return expires_at.strftime("%Y-%m-%d %H:%M:%S")


async def get_license_state() -> dict:
    settings = await db.get_bot_settings()
    expires_at = settings["expires_at"]
    expired = bool(expires_at and datetime.now() > expires_at)
    effective_channel_limit = 0
    limits = [
        limit for limit in (
            settings["content_limit"],
            settings["fsub_limit"],
            settings["group_limit"]
        ) if limit > 0
    ]
    if limits:
        effective_channel_limit = min(limits)

    settings["expired"] = expired
    settings["effective_channel_limit"] = effective_channel_limit
    return settings


def is_dev(user_id: int) -> bool:
    return user_id in config.dev_id


def build_license_text(state: dict) -> str:
    status = "Aktif" if state["is_active"] and not state["expired"] else "Nonaktif"
    remaining_text = "0 hari"
    if state["is_active"] and not state["expired"] and state["expires_at"]:
        remaining_delta = state["expires_at"] - datetime.now()
        remaining_days = max(0, math.ceil(remaining_delta.total_seconds() / 86400))
        remaining_text = f"{remaining_days} hari"
    return (
        f"Status bot: {status}\n"
        f"Expired: {format_expiry(state['expires_at'])}\n"
        f"Sisa hari: {remaining_text}\n"
        f"Limit konten: {state['content_limit'] or 'Unlimited'}\n"
        f"Limit fsub: {state['fsub_limit'] or 'Unlimited'}\n"
        f"Limit group: {state['group_limit'] or 'Unlimited'}\n"
        f"Limit efektif daftar channel: {state['effective_channel_limit'] or 'Unlimited'}"
    )


async def ensure_bot_available(m: Message) -> bool:
    if is_dev(m.from_user.id):
        return True

    state = await get_license_state()
    if state["is_active"] and not state["expired"]:
        return True

    reason = "Bot belum diaktifkan oleh developer." if not state["is_active"] else (
        f"Masa aktif bot sudah habis pada {format_expiry(state['expires_at'])}."
    )
    await m.reply(f"{reason}\nHubungi developer untuk aktivasi.")
    return False


async def ensure_bot_available_callback(cb: CallbackQuery) -> bool:
    if is_dev(cb.from_user.id):
        return True

    state = await get_license_state()
    if state["is_active"] and not state["expired"]:
        return True

    reason = "Bot belum diaktifkan oleh developer." if not state["is_active"] else (
        f"Masa aktif bot sudah habis pada {format_expiry(state['expires_at'])}."
    )
    await cb.answer(reason, show_alert=True)
    return False


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


@bot.on_message(filters.command("license") & filters.private)
async def license_handler(c: Client, m: Message):
    if not is_dev(m.from_user.id) and m.from_user.id not in config.owner_id:
        return await m.reply("Hanya developer atau owner yang bisa melihat status lisensi bot.")

    state = await get_license_state()
    return await m.reply(build_license_text(state))


@bot.on_message(filters.command("cek") & filters.private)
async def cek_handler(c: Client, m: Message):
    if not is_dev(m.from_user.id) and m.from_user.id not in config.owner_id:
        return await m.reply("Hanya developer atau owner yang bisa mengecek status bot.")

    args = m.text.split(maxsplit=1)
    me = await c.get_me()
    if len(args) > 1:
        target = args[1].strip().lstrip("@")
        valid_targets = {str(me.id)}
        if me.username:
            valid_targets.add(me.username.lower())
        if target.lower() not in valid_targets:
            return await m.reply("Bot ID atau username tidak cocok dengan bot ini.")

    state = await get_license_state()
    return await m.reply(
        f"Bot ID: {me.id}\nUsername: @{me.username or '-'}\n{build_license_text(state)}"
    )


@bot.on_message(filters.command("sewa") & filters.private)
async def sewa_handler(c: Client, m: Message):
    if not is_dev(m.from_user.id):
        return await m.reply("Hanya developer yang bisa mengaktifkan bot.")

    args = m.text.split()
    if len(args) < 2 or not args[1].isdigit():
        return await m.reply("Gunakan: /sewa <jumlah_hari>\nContoh: /sewa 30")

    total_days = int(args[1])
    if total_days <= 0:
        return await m.reply("Jumlah hari harus lebih dari 0.")

    state = await get_license_state()
    base_time = datetime.now()
    if state["is_active"] and not state["expired"] and state["expires_at"]:
        base_time = state["expires_at"]

    expires_at = base_time + timedelta(days=total_days)
    await db.set_setting("is_active", "1")
    await db.set_setting("expires_at", expires_at.isoformat())
    state = await get_license_state()
    return await m.reply(
        f"Masa aktif bot berhasil ditambah {total_days} hari.\n{build_license_text(state)}"
    )


@bot.on_message(filters.command("deactivate") & filters.private)
async def deactivate_handler(c: Client, m: Message):
    if not is_dev(m.from_user.id):
        return await m.reply("Hanya developer yang bisa menonaktifkan bot.")

    await db.set_setting("is_active", "0")
    state = await get_license_state()
    return await m.reply(f"Bot berhasil dinonaktifkan.\n{build_license_text(state)}")


@bot.on_message(filters.command("limitkonten") & filters.private)
async def limitkonten_handler(c: Client, m: Message):
    if not is_dev(m.from_user.id):
        return await m.reply("Hanya developer yang bisa mengatur limit bot.")

    args = m.text.split()
    if len(args) < 2 or not args[1].isdigit():
        return await m.reply(
            "Gunakan: /limitkonten <jumlah>\n"
            "Isi 0 jika ingin unlimited. Contoh: /limitkonten 5"
        )

    content_limit = int(args[1])
    await db.set_setting("content_limit", str(content_limit))
    state = await get_license_state()
    return await m.reply(f"Limit konten bot diperbarui.\n{build_license_text(state)}")


# Bot management command untuk menambahkan fsub channel secara dinamis
@bot.on_message(filters.command("addgc") & filters.private)
async def addgc_handler(c: Client, m: Message):
    if not await ensure_bot_available(m):
        return

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

    state = await get_license_state()
    effective_limit = state["effective_channel_limit"]
    current_total = await db.get_fsub_channel_count()
    if effective_limit and current_total >= effective_limit:
        return await m.reply(
            f"Limit channel bot sudah penuh ({effective_limit}). Hubungi developer untuk menaikkan limit."
        )

    await db.add_fsub_channel(channel)
    return await m.reply(f"Berhasil menambahkan channel fsub: {channel}")


@bot.on_message(filters.command("listgc") & filters.private)
async def listgc_handler(c: Client, m: Message):
    if not await ensure_bot_available(m):
        return

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
    if not await ensure_bot_available(m):
        return

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
            await safe_send_document(
                config.log_channel,
                document=str(backup_path),
                caption=f"Backup dibuat oleh owner pada {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
    except Exception as e:
        return await m.reply(f"❌ Gagal membuat backup: {e}")


@bot.on_message(filters.command("listbackup") & filters.private)
async def listbackup_handler(c: Client, m: Message):
    if not await ensure_bot_available(m):
        return

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
    if not await ensure_bot_available(m):
        return

    if not config.owner_id:
        return await m.reply(
            "OWNER_ID belum dikonfigurasi. Tambahkan OWNER_ID di local.env atau environment variable."
        )

    if m.from_user.id not in config.owner_id:
        return await m.reply("Hanya owner bot yang dapat menggunakan perintah ini.")

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
            await safe_send_message(
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
    if not await ensure_bot_available(m):
        return

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


@bot.on_callback_query(filters.regex("^aboutbot$"))
async def aboutbot_handler(c: Client, cb: CallbackQuery):
    await cb.answer()
    await cb.message.reply(
        "Bot ini dipakai untuk mengirim pesan atau media secara anonim ke channel yang sudah didaftarkan owner."
    )


@bot.on_callback_query(filters.regex("^aboutdev$"))
async def aboutdev_handler(c: Client, cb: CallbackQuery):
    await cb.answer()
    await cb.message.reply(
        "Info developer belum diatur di project ini. Kamu bisa ganti teks ini sesuai identitas admin bot."
    )


# Handler pesan teks/media
@bot.on_message((filters.text | filters.media) & ~filters.sticker)
async def send_media_(c: Client, m: Message):
    if m.chat.type != "private":
        return
    if m.text and m.text.startswith("/"):
        return
    if not await ensure_bot_available(m):
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
    if not await ensure_bot_available_callback(cb):
        return

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
            caption=m.reply_to_message.caption or None
        )
        
        await m.delete()
        sent_message_link = build_message_link(x.chat, x.message_id)
        reply_markup = None
        if sent_message_link:
            reply_markup = InlineKeyboardMarkup([[
                InlineKeyboardButton("Klik disini", url=sent_message_link)
            ]])
        await m.reply(
            "**Pesan berhasil terkirim, silakan lihat dengan klik tombol dibawah ini!**",
            reply_markup=reply_markup
        )

        if config.log_channel:
            try:
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
            except Exception as log_exc:
                print(f"Gagal kirim log pesan: {log_exc}")
    except Exception as e:
        await cb.answer(f"Error: {e}", show_alert=True)


# Main loop
async def main():
    try:
        missing_config = config.missing_required()
        if missing_config:
            print(f"Config wajib belum diisi: {', '.join(missing_config)}")
            return
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
