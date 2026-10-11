"""Общие помощники: безопасное редактирование и фоновые рассылки."""
import asyncio
import logging

from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter

log = logging.getLogger(__name__)
_tasks: set = set()


async def safe_edit(msg, text: str, markup=None) -> None:
    try:
        await msg.edit_text(text, reply_markup=markup)
    except TelegramBadRequest as e:
        if "not modified" not in str(e):
            raise


async def _run(bot, user_ids, text, markup, report_to) -> None:
    ok = 0
    for uid in user_ids:
        for _ in range(2):
            try:
                await bot.send_message(uid, text, reply_markup=markup)
                ok += 1
                break
            except TelegramRetryAfter as e:
                await asyncio.sleep(e.retry_after + 1)
            except Exception:
                break
        await asyncio.sleep(0.05)  # ~20 сообщений в секунду, в пределах лимитов Telegram
    if report_to:
        try:
            await bot.send_message(
                report_to, f"📣 Рассылка завершена: доставлено <b>{ok}</b> из <b>{len(user_ids)}</b>."
            )
        except Exception:
            pass


def start_broadcast(bot, user_ids, text: str, markup=None, report_to: int | None = None) -> None:
    """Запускает рассылку в фоне, не блокируя бота."""
    ids = list(user_ids)
    if not ids:
        return
    task = asyncio.create_task(_run(bot, ids, text, markup, report_to))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
