import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_GROUP_ID = int(os.getenv("ADMIN_GROUP_ID", "0"))
APPLICATIONS_TOPIC_ID = int(os.getenv("APPLICATIONS_TOPIC_ID") or 0) or None
# Топики админ-группы: обращения и жалобы (если пусто — пишем в общий топик)
SUPPORT_TOPIC_ID = int(os.getenv("SUPPORT_TOPIC_ID") or 0) or None
COMPLAINTS_TOPIC_ID = int(os.getenv("COMPLAINTS_TOPIC_ID") or 0) or None


def _channel(raw: str):
    raw = raw.strip()
    if not raw:
        return "@flz_team"                      # канал по умолчанию: t.me/flz_team
    if raw.lstrip("-").isdigit():
        return int(raw)
    return raw if raw.startswith("@") else "@" + raw.split("/")[-1]


# Канал, из которого берём число участников (@username или числовой ID)
CHANNEL = _channel(os.getenv("CHANNEL_ID", ""))
# Публичный канал (@username) -> обычная ссылка; закрытый (числовой ID) -> бот выдаёт личную одноразовую ссылку
CHANNEL_URL = f"https://t.me/{CHANNEL.lstrip('@')}" if isinstance(CHANNEL, str) else None

def _optional_chat(raw: str):
    raw = raw.strip()
    if not raw:
        return None
    if raw.lstrip("-").isdigit():
        return int(raw)
    return raw if raw.startswith("@") else "@" + raw.split("/")[-1]


# Канал для заявок «Поиск команды» (бот должен быть админом с правом публикации)
TEAM_CHANNEL_ID = _optional_chat(os.getenv("TEAM_CHANNEL_ID", ""))

# Эти пользователи всегда получают роль «Владелец»
ADMIN_IDS = {int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()}
DB_PATH = os.getenv("DB_PATH", "bot.db")
# Папка для ежедневных резервных копий базы
BACKUP_DIR = os.getenv("BACKUP_DIR", "backups")
# Часовой пояс для мероприятий и календаря
TIMEZONE = os.getenv("TIMEZONE", "Europe/Moscow")
# Ключ Steam Web API (https://steamcommunity.com/dev/apikey). Без него привязка Steam отключена
STEAM_API_KEY = os.getenv("STEAM_API_KEY", "").strip()

# Куда бот присылает ежедневные копии базы (ID чата или @канал). По умолчанию — личка первого владельца
BACKUP_CHAT_ID = _optional_chat(os.getenv("BACKUP_CHAT_ID", "")) or (min(ADMIN_IDS) if ADMIN_IDS else None)
BACKUP_EVERY_HOURS = max(1, int(os.getenv("BACKUP_EVERY_HOURS") or 24))
