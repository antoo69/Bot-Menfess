#!/bin/bash

sudo apt-get update -y && sudo apt-get full-upgrade -y
sudo apt-get install -y --no-install-recommends \
    ffmpeg git neofetch apt-utils libmediainfo0v5 \
    libgl1 libglx-mesa0 libglib2.0-0 \
    fonts-noto-color-emoji tmux \
    python3-venv python3-pip sqlite3 net-tools lsof

sudo apt-get clean
sudo rm -rf /var/lib/apt/lists/*
