"""Служебные команды для управления с телефона: /status и /backup."""
import os
import platform
import time

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import FSInputFile, Message

import config
import timeutil
from database import db

router = Router()
STARTED = time.time()


def _uptime() -> str:
    secs = int(time.time() - STARTED)
    d, rem = divmod(secs, 86400)
    h, rem = divmod(rem, 3600)
    return f"{d} д {h} ч {rem // 60} мин" if d else f"{h} ч {rem // 60} мин"


@router.message(Command("status"), F.chat.type == "private")
async def status(message: Message):
    if await db.get_level(message.from_user.id) < 3:  # заместитель и выше
        return
    s = await db.db_stats()
    size = os.path.getsize(config.DB_PATH) / 1024 if os.path.exists(config.DB_PATH) else 0
    maintenance = "включены 🔴" if await db.get_setting("maintenance") == "1" else "выключены 🟢"
    await message.answer(
        "🩺 <b>Состояние бота</b>\n"
        "▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n"
        f"⏱ Работает: <b>{_uptime()}</b>\n"
        f"🕒 Время сервера: <b>{timeutil.local_now():%d.%m.%Y %H:%M} {timeutil.TZ_LABEL}</b>\n"
        f"🐍 Python: {platform.python_version()}\n"
        f"💾 База: <b>{size:.0f} КБ</b>\n"
        f"👥 Пользователей: <b>{s['users']}</b> (участников: {s['members']})\n"
        f"📝 Анкет в очереди: <b>{s['pending']}</b>\n"
        f"✉️ Открытых обращений: <b>{s['open_tickets']}</b>\n"
        f"🎮 Привязано Steam: <b>{s['steam_linked']}</b>\n"
        f"🔑 Ключ Steam: {'задан ✅' if config.STEAM_API_KEY else 'не задан ⚠️'}\n"
        f"🛠 Тех. работы: {maintenance}"
    )


@router.message(Command("backup"), F.chat.type == "private")
async def backup(message: Message):
    if await db.get_level(message.from_user.id) < 5:  # только владелец
        return
    path = os.path.join(config.BACKUP_DIR, f"manual_{timeutil.local_now():%Y-%m-%d_%H-%M}.db")
    await db.backup_to(path)
    try:
        await message.answer_document(FSInputFile(path), caption="💾 Резервная копия базы данных")
    finally:
        if os.path.exists(path):
            os.remove(path)


@router.message(Command("export"), F.chat.type == "private")
async def export(message: Message):
    if await db.get_level(message.from_user.id) < 5:  # только владелец
        return
    path = os.path.join(config.BACKUP_DIR, f"export_manual_{timeutil.local_now():%Y-%m-%d_%H-%M}.zip")
    await db.export_csv_zip(path)
    try:
        await message.answer_document(
            FSInputFile(path), caption="📊 Выгрузка всех таблиц в CSV (открывается в Excel и Google Таблицах)"
        )
    finally:
        if os.path.exists(path):
            os.remove(path)
