"""Фоновые задачи бота."""
import asyncio
import glob
import logging
import os

from aiogram.types import FSInputFile

import config
import steam
import timeutil
import ui
from database import db
from utils import start_broadcast

log = logging.getLogger(__name__)


async def reminder_loop(bot) -> None:
    """Раз в минуту напоминает записавшимся о мероприятиях, которые начнутся в течение часа."""
    while True:
        try:
            for e in await db.events_to_remind():
                await db.mark_reminded(e["id"])
                start_broadcast(bot, await db.rsvp_user_ids(e["id"], only_notify=True), ui.event_reminder(e))
        except Exception as ex:
            log.error("Ошибка в напоминаниях: %s", ex)
        await asyncio.sleep(60)


async def steam_loop() -> None:
    """Раз в 6 часов обновляет часы у привязанных аккаунтов, которые не синхронизировались сутки."""
    await asyncio.sleep(60)
    while True:
        try:
            for u in await db.steam_users_due(timeutil.in_days(-1)):
                try:
                    hours = await steam.get_rust_hours(u["steam_id"])
                    if hours is not None:
                        await db.update_steam_hours(u["tg_id"], hours)
                    else:
                        await db.touch_steam_sync(u["tg_id"])
                except steam.SteamError as e:
                    log.warning("Steam sync %s: %s", u["tg_id"], e)
                await asyncio.sleep(0.5)
        except Exception as ex:
            log.error("Ошибка синхронизации Steam: %s", ex)
        await asyncio.sleep(6 * 3600)


async def backup_loop(bot) -> None:
    """Копия базы + выгрузка таблиц в CSV: сохраняются на сервере и присылаются в Telegram (вне сервера)."""
    await asyncio.sleep(300)
    while True:
        try:
            stamp = timeutil.local_now()
            db_path = os.path.join(config.BACKUP_DIR, f"bot_{stamp:%Y-%m-%d_%H-%M}.db")
            csv_path = os.path.join(config.BACKUP_DIR, f"export_{stamp:%Y-%m-%d_%H-%M}.zip")
            healthy = await db.integrity_ok()
            await db.backup_to(db_path)
            await db.export_csv_zip(csv_path)
            for pattern in ("bot_*.db", "export_*.zip"):  # на сервере храним последние 14
                for old in sorted(glob.glob(os.path.join(config.BACKUP_DIR, pattern)))[:-14]:
                    os.remove(old)
            log.info("Резервная копия сохранена: %s", db_path)

            if config.BACKUP_CHAT_ID:
                caption = f"💾 Копия базы · {stamp:%d.%m.%Y %H:%M} {timeutil.TZ_LABEL}"
                if not healthy:
                    caption += "\n⚠️ Проверка целостности нашла проблемы — проверь базу!"
                await bot.send_document(config.BACKUP_CHAT_ID, FSInputFile(db_path), caption=caption)
                await bot.send_document(
                    config.BACKUP_CHAT_ID, FSInputFile(csv_path),
                    caption="📊 Выгрузка таблиц (CSV — открывается в Excel и Google Таблицах)",
                )
        except Exception as ex:
            log.error("Ошибка резервного копирования: %s", ex)
        await asyncio.sleep(config.BACKUP_EVERY_HOURS * 3600)
