import asyncio
import logging
import os
import sys
from logging.handlers import RotatingFileHandler

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ErrorEvent

import config
import tasks
from database import db
from handlers import (
    admin, admin_manage, anketa, channel, composition, emergency, events, facts, ops, polls,
    profile, reputation, rules, settings, start, stats, steam, support, team, tutorial,
)
from middlewares.access import AccessMiddleware
from middlewares.home import HomeButtonMiddleware

log = logging.getLogger("rustbot")


def setup_logging() -> None:
    os.makedirs("logs", exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    file = RotatingFileHandler("logs/bot.log", maxBytes=5_000_000, backupCount=5, encoding="utf-8")
    file.setFormatter(fmt)
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers = [console, file]


def check_config() -> None:
    errors = []
    if not config.BOT_TOKEN:
        errors.append("BOT_TOKEN не задан в .env")
    if not config.ADMIN_GROUP_ID:
        errors.append("ADMIN_GROUP_ID не задан в .env")
    if not config.ADMIN_IDS:
        errors.append("ADMIN_IDS не задан в .env (нужен хотя бы один владелец)")
    if errors:
        for e in errors:
            log.error(e)
        sys.exit(1)


async def on_error(event: ErrorEvent) -> bool:
    """Любая необработанная ошибка попадает в лог, а пользователь видит понятное сообщение."""
    log.error("Необработанная ошибка в обработчике", exc_info=event.exception)
    text = "⚠️ Что-то пошло не так. Попробуй ещё раз или нажми /start."
    try:
        if event.update.callback_query:
            await event.update.callback_query.answer(text, show_alert=True)
        elif event.update.message:
            await event.update.message.answer(text)
    except Exception:
        pass
    return True


async def main():
    setup_logging()
    check_config()
    await db.init()
    await db.seed_owners(config.ADMIN_IDS)

    bot = Bot(config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    bot.session.middleware(HomeButtonMiddleware())  # кнопка «Главное меню» под каждым уведомлением
    dp = Dispatcher(storage=MemoryStorage())

    dp.message.outer_middleware(AccessMiddleware())
    dp.callback_query.outer_middleware(AccessMiddleware())
    dp.errors.register(on_error)

    # start первым: /start должен сбрасывать любое состояние
    for module in (
        start, ops, anketa, tutorial, rules, profile, composition, admin, admin_manage, reputation,
        support, polls, events, team, facts, emergency, stats, settings, steam, channel, broadcasts, user_messaging,
    ):
        dp.include_router(module.router)

    background = [
        asyncio.create_task(tasks.reminder_loop(bot)),
        asyncio.create_task(tasks.subscription_check_loop(bot)),
        asyncio.create_task(tasks.backup_loop(bot)),
    ]
    if config.STEAM_API_KEY:
        background.append(asyncio.create_task(tasks.steam_loop()))

    me = await bot.get_me()
    log.info("Бот @%s запущен", me.username)
    try:
        await dp.start_polling(bot)
    finally:
        for t in background:
            t.cancel()
        await bot.session.close()
        await db.close()  # все данные записаны на диск, WAL сведён в основной файл


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
