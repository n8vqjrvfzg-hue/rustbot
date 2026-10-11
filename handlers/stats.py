"""Статистика админов — для заместителя и выше."""
from aiogram import F, Router
from aiogram.types import CallbackQuery

import ui
from database import db
from handlers.common import need_level
from keyboards import extras as kb
from utils import safe_edit
import timeutil

router = Router()
MIN_LEVEL = 3  # заместитель и выше


def _since(days: int) -> str:
    return "1970-01-01 00:00:00" if days == 0 else timeutil.in_days(-days)


async def _overview(cb: CallbackQuery, days: int) -> None:
    stats = await db.admin_stats(_since(days))
    staff = {u["tg_id"]: u for u in await db.staff_users()}
    rows = []
    for aid in set(stats) | set(staff):
        u = staff.get(aid) or await db.get_user(aid)
        if not u:
            continue
        actions = stats.get(aid, {})
        rows.append((u, sum(actions.values()), ui.stat_counts(actions)))
    rows.sort(key=lambda r: (-r[1], r[0]["tg_id"]))
    await safe_edit(
        cb.message,
        ui.stats_overview(kb.PERIODS.get(days, "Всё время"), rows),
        kb.stats_kb([(u, total, c) for u, total, c in rows], days),
    )


@router.callback_query(F.data == "adm:stats")
async def stats_home(cb: CallbackQuery):
    if await need_level(cb, MIN_LEVEL) is None:
        return
    await _overview(cb, 0)
    await cb.answer()


@router.callback_query(F.data.startswith("adm:stp:"))
async def stats_period(cb: CallbackQuery):
    if await need_level(cb, MIN_LEVEL) is None:
        return
    days = int(cb.data.split(":")[2])
    if days not in kb.PERIODS:
        return await cb.answer()
    await _overview(cb, days)
    await cb.answer()


@router.callback_query(F.data.startswith("adm:stu:"))
async def stats_user(cb: CallbackQuery):
    if await need_level(cb, MIN_LEVEL) is None:
        return
    _, _, aid, days = cb.data.split(":")
    days = int(days)
    u = await db.get_user(int(aid))
    if not u or days not in kb.PERIODS:
        return await cb.answer("Данные недоступны.", show_alert=True)
    actions = (await db.admin_stats(_since(days))).get(u["tg_id"], {})
    await safe_edit(
        cb.message,
        ui.stats_detail(u, sum(actions.values()), ui.stat_counts(actions), kb.PERIODS[days]),
        kb.stats_detail_kb(days),
    )
    await cb.answer()
