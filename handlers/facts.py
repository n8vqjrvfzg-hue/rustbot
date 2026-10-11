"""Факты о Rust: подбираются по часовому рангу участника. Админы могут добавлять свои."""
import random

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

import ui
from database import db
from facts_data import FACTS, tier_for
from handlers.common import get_member, need_level
from keyboards import extras as kb
from utils import safe_edit

router = Router()
MIN_LEVEL = 2  # администратор и выше добавляет факты


class FactNew(StatesGroup):
    text = State()


async def _pool(tier: str) -> list:
    """Встроенные факты уровня + добавленные админами."""
    pool = list(FACTS[tier])
    for row in reversed(await db.custom_facts(tier)):
        pool.append(("💡 Факт от сообщества", row["text"]))
    return pool


async def _show(cb: CallbackQuery, tier: str, cur: int = -1) -> None:
    pool = await _pool(tier)
    choices = [i for i in range(len(pool)) if i != cur] or [0]
    i = random.choice(choices)
    title, text = pool[i]
    await safe_edit(cb.message, ui.fact_text(tier, i, len(pool), title, text), kb.facts_kb(tier, i))


# ---------- участники ----------

@router.callback_query(F.data == "facts")
async def facts_home(cb: CallbackQuery):
    me = await get_member(cb)
    if not me:
        return
    await _show(cb, tier_for(me["hours"]))
    await cb.answer()


@router.callback_query(F.data.startswith("facts:n:"))
async def facts_next(cb: CallbackQuery):
    if not await get_member(cb):
        return
    _, _, tier, cur = cb.data.split(":")
    if tier not in FACTS:
        return await cb.answer()
    await _show(cb, tier, int(cur) if cur.lstrip("-").isdigit() else -1)
    await cb.answer()


@router.callback_query(F.data.startswith("facts:t:"))
async def facts_tier(cb: CallbackQuery):
    if not await get_member(cb):
        return
    tier = cb.data.split(":")[2]
    if tier not in FACTS:
        return await cb.answer()
    await _show(cb, tier)
    await cb.answer()


# ---------- админы: свои факты ----------

@router.callback_query(F.data == "adm:facts")
async def admin_home(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    if await need_level(cb, MIN_LEVEL) is None:
        return
    total = len(await db.custom_facts())
    await safe_edit(cb.message, ui.facts_admin_text(total), kb.facts_admin_kb())
    await cb.answer()


@router.callback_query(F.data == "adm:fn")
async def admin_new_tier(cb: CallbackQuery):
    if await need_level(cb, MIN_LEVEL) is None:
        return
    await safe_edit(cb.message, ui.fact_tier_prompt(), kb.fact_tier_kb())
    await cb.answer()


@router.callback_query(F.data.startswith("adm:fn:"))
async def admin_new_text(cb: CallbackQuery, state: FSMContext):
    if await need_level(cb, MIN_LEVEL) is None:
        return
    tier = cb.data.split(":")[2]
    if tier not in FACTS:
        return await cb.answer()
    await state.set_state(FactNew.text)
    await state.update_data(tier=tier)
    await safe_edit(cb.message, ui.fact_new_prompt(tier), kb.fact_cancel_kb())
    await cb.answer()


@router.message(FactNew.text, F.text)
async def admin_save(message: Message, state: FSMContext):
    if await db.get_level(message.from_user.id) < MIN_LEVEL:
        return await state.clear()
    text = message.text.strip()[:600]
    if len(text) < 10:
        return await message.answer("⚠️ Слишком коротко. Напиши факт подробнее.")
    tier = (await state.get_data())["tier"]
    fid = await db.add_custom_fact(tier, text, message.from_user.id)
    await db.log_action(message.from_user.id, "fact_add", None, f"#{fid} {tier}")
    await state.clear()
    await message.answer(f"✅ Факт #{fid} добавлен!", reply_markup=kb.facts_admin_kb())


@router.callback_query(F.data == "adm:fl")
async def admin_list(cb: CallbackQuery):
    if await need_level(cb, MIN_LEVEL) is None:
        return
    rows = await db.custom_facts(limit=15)
    text = f"{ui.header('📋', 'ДОБАВЛЕННЫЕ ФАКТЫ')}\n\n" + ("Последние 15 👇" if rows else "Пока ничего не добавлено.")
    await safe_edit(cb.message, text, kb.fact_list_kb(rows))
    await cb.answer()


@router.callback_query(F.data.startswith("adm:fv:"))
async def admin_view(cb: CallbackQuery):
    if await need_level(cb, MIN_LEVEL) is None:
        return
    row = await db.get_custom_fact(int(cb.data.split(":")[2]))
    if not row:
        return await cb.answer("Факт не найден.", show_alert=True)
    await safe_edit(cb.message, ui.fact_view_text(row), kb.fact_view_kb(row["id"]))
    await cb.answer()


@router.callback_query(F.data.startswith("adm:fd:"))
async def admin_delete(cb: CallbackQuery):
    if await need_level(cb, MIN_LEVEL) is None:
        return
    fid = int(cb.data.split(":")[2])
    await db.delete_custom_fact(fid)
    await db.log_action(cb.from_user.id, "fact_delete", None, f"#{fid}")
    rows = await db.custom_facts(limit=15)
    text = f"{ui.header('📋', 'ДОБАВЛЕННЫЕ ФАКТЫ')}\n\n🗑 Факт удалён.\n\n" + ("Последние 15 👇" if rows else "Пока ничего не добавлено.")
    await safe_edit(cb.message, text, kb.fact_list_kb(rows))
    await cb.answer("Удалено")
