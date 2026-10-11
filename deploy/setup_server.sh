#!/usr/bin/env bash
# Первичная настройка сервера (Ubuntu 22.04/24.04) под бота. Запускать от root ОДИН раз:
#   bash /opt/rustbot/deploy/setup_server.sh
set -e
cd /opt/rustbot

echo "==> Устанавливаю пакеты"
apt-get update -y
apt-get install -y python3 python3-venv python3-pip unzip ufw curl

echo "==> Пользователь bot и часовой пояс сервера (МСК, чтобы логи читались удобно)"
id bot >/dev/null 2>&1 || adduser --disabled-password --gecos "" bot
timedatectl set-timezone Europe/Moscow || true

echo "==> Виртуальное окружение и зависимости"
python3 -m venv venv
./venv/bin/pip install --upgrade pip -q
./venv/bin/pip install -r requirements.txt -q

echo "==> Файл настроек"
[ -f .env ] || cp .env.example .env
chmod 600 .env
chown -R bot:bot /opt/rustbot

echo "==> Автозапуск и команда botctl"
cp deploy/rustbot.service /etc/systemd/system/rustbot.service
systemctl daemon-reload
install -m 755 deploy/botctl /usr/local/bin/botctl

echo "==> Фаервол: открыт только SSH"
ufw allow OpenSSH >/dev/null
ufw --force enable >/dev/null

echo
echo "==> Проверка доступа к Telegram и Steam с этого сервера"
curl -s -o /dev/null -m 10 -w "api.telegram.org      -> HTTP %{http_code}\n" https://api.telegram.org || echo "api.telegram.org      -> НЕТ ДОСТУПА"
curl -s -o /dev/null -m 10 -w "api.steampowered.com  -> HTTP %{http_code}\n" https://api.steampowered.com || echo "api.steampowered.com  -> НЕТ ДОСТУПА"

echo
echo "Готово. Дальше:"
echo "  1) заполни настройки:   nano /opt/rustbot/.env"
echo "  2) запусти бота:        systemctl enable --now rustbot"
echo "  3) смотри логи:         botctl logs"
