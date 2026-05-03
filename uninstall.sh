#!/bin/bash
set -e

SERVICE_NAME=$(basename "$(pwd)")
REPO_DIR="$(cd "$(dirname "$0")"; pwd)"
VENV_DIR="$REPO_DIR/venv"

echo "🛑 Menghentikan dan menghapus systemd service '$SERVICE_NAME'..."

if systemctl cat "$SERVICE_NAME" > /dev/null 2>&1; then
    sudo systemctl stop "$SERVICE_NAME" || true
    sudo systemctl disable "$SERVICE_NAME" || true
    sudo rm -f "/etc/systemd/system/$SERVICE_NAME.service"
    sudo systemctl daemon-reload
    echo "✅ Service '$SERVICE_NAME' berhasil dihapus."
else
    echo "ℹ️ Service '$SERVICE_NAME' tidak ditemukan atau sudah dinonaktifkan."
fi

# Hapus virtual environment jika ada
if [ -d "$VENV_DIR" ]; then
    echo "🧹 Menghapus virtual environment..."
    rm -rf "$VENV_DIR"
    echo "✅ Virtual environment dihapus."
else
    echo "ℹ️ Virtual environment tidak ditemukan."
fi


echo "🧼 Pembersihan selesai!"
