#!/usr/bin/env bash
# Обновление бота на сервере: запускать из любой папки командой  sudo bash /opt/rustbot/deploy/update.sh
set -e
cd /opt/rustbot
chown -R bot:bot /opt/rustbot
sudo -u bot /opt/rustbot/venv/bin/pip install -r requirements.txt -q
systemctl restart rustbot
sleep 3
systemctl is-active rustbot
journalctl -u rustbot -n 15 --no-pager
