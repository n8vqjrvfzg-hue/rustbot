"""Минимальные настройки бота — для заместителя и выше."""
from aiogram import F, Router
from aiogram.types import CallbackQuery

import ui
from database import db
from handlers.common import need_level
from keyboards import extras as kb
from utils import safe_edit

router = Router()
MIN_LEVEL = 3

TOGGLES = {"apps_open": "1", "autoban": "0"}
REP_LIMITS = ["3", "5", "10"]


async def _values() -> dict:
    return {
        "apps_open": await db.get_setting("apps_open", "1"),
        "autoban": await db.get_setting("autoban", "0"),
        "rep_per_day": await db.get_setting("rep_per_day", "5"),
    }


async def _render(cb: CallbackQuery) -> None:
    v = await _values()
    await safe_edit(cb.message, ui.settings_text(v), kb.settings_kb(v))


@router.callback_query(F.data == "adm:settings")
async def settings_home(cb: CallbackQuery):
    if await need_level(cb, MIN_LEVEL) is None:
        return
    await _render(cb)
    await cb.answer()


@router.callback_query(F.data.startswith("adm:set:"))
async def settings_change(cb: CallbackQuery):
    if await need_level(cb, MIN_LEVEL) is None:
        return
    key = cb.data.split(":")[2]
    if key in TOGGLES:
        new = "0" if await db.get_setting(key, TOGGLES[key]) == "1" else "1"
    elif key == "rep_per_day":
        cur = await db.get_setting(key, "5")
        new = REP_LIMITS[(REP_LIMITS.index(cur) + 1) % len(REP_LIMITS)] if cur in REP_LIMITS else "5"
    else:
        return await cb.answer()
    await db.set_setting(key, new)
    await db.log_action(cb.from_user.id, "setting", None, f"{key}={new}")
    await _render(cb)
    await cb.answer("Сохранено")
