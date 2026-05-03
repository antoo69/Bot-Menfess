# MENFESS BOT

### With Heroku
[![Deploy](https://www.herokucdn.com/deploy/button.svg)](https://www.heroku.com/deploy?template=https://github.com/bulanbintang69/percobaan-2)


## I FIND A BUGS

## Backup dan Restore

Bot sekarang mendukung backup SQLite otomatis setiap jam 00:00, dan akan mengirim file backup (dalam format `.zip`) ke `LOG_CHANNEL` jika dikonfigurasi.

### Perintah backup (owner)

- `/backup` — buat backup manual file `bot.db` dan kirim file `.db` ke chat
  - Juga otomatis dikirim ke `LOG_CHANNEL` jika dikonfigurasi

### Perintah restore (owner)

**Pilihan 1: Dari folder backup lokal**
- `/restore <nama_backup.db>` — restore dari backup yang ada di folder `backups/`
  - Contoh: `/restore bot_backup_20240503_000000.db`
- `/restore latest` — restore dari backup terbaru

**Pilihan 2: Upload file `.db`**
- Reply pesan dengan file `.db` (dokumen), lalu ketik `/restore`
- Bot akan langsung menggunakan file yang kamu upload

### Backup otomatis (setiap 00:00)

- Bot membuat backup otomatis setiap jam 00:00
- File backup dikompres dalam format `.zip` dan dikirim ke `LOG_CHANNEL`
- Isi file `.zip` adalah file `bot.db` dengan nama format: `bot_backup_YYYYMMDD_HHMMSS.db`

### Konfigurasi

Pastikan `local.env` memiliki:

```env
OWNER_ID=123456789
BACKUP_DIR=backups
LOG_CHANNEL=-1002351111178
```

### Catatan

- Folder default backup adalah `backups/`
- Hanya owner yang bisa menjalankan perintah backup/restore
- Saat restore berhasil, bot akan meminta di-restart untuk hasil optimal

## Penggunaan /addgc

Bot sekarang dapat menambahkan channel/group fsub lewat perintah private chat dari owner bot. Channel yang di-add akan berfungsi sebagai:
1. Syarat wajib join untuk user bisa pakai bot (FSUB check)
2. Pilihan tujuan pengiriman pesan

Tambahkan `OWNER_ID` di `local.env`:

```env
OWNER_ID=123456789
```

Gunakan perintah:

```bash
/addgc <username atau id grup/channel>
```

Contoh:

```bash
/addgc BestieVirtual
/addgc -1001234567890
```

### Alur penggunaan

1. Owner jalankan `/addgc BestieVirtual` untuk tambah channel
2. User `/start` → bot akan cek apakah user sudah join BestieVirtual
3. User join, lalu kirim pesan ke bot
4. Bot tampilkan tombol pilihan channel (yang sudah di-add via `/addgc`)
5. User pilih channel mana yang dituju, pesan dikirim ke sana secara anonim
