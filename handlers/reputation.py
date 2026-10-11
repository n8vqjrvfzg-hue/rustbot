"""Репутация (+rep / -rep, топ) и жалобы на участников."""
import html
import logging

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

import config
import roles
import ui
from database import db
from handlers.common import get_member
from keyboards import rep as kb

router = Router()
log = logging.getLogger(__name__)


class RepFind(StatesGroup):
    query = State()


class Report(StatesGroup):
    text = State()


@router.callback_query(F.data == "rep")
async def rep_menu(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    me = await get_member(cb)
    if not me:
        return
    left = await db.rep_votes_left(me["tg_id"])
    await cb.message.edit_text(ui.rep_menu_text(me, left), reply_markup=kb.rep_menu_kb())
    await cb.answer()


@router.callback_query(F.data == "rep:top")
async def rep_top(cb: CallbackQuery):
    me = await get_member(cb)
    if not me:
        return
    rows = await db.top_reputation(10)
    rank = await db.rep_rank(me["tg_id"])
    await cb.message.edit_text(ui.top_text(rows, rank, me["reputation"]), reply_markup=kb.back_to_rep())
    await cb.answer()


# ---------- выбор участника ----------

@router.callback_query(F.data.startswith("rep:find:"))
async def find_start(cb: CallbackQuery, state: FSMContext):
    if not await get_member(cb):
        return
    mode = cb.data.split(":")[2]
    if mode not in ("vote", "report"):
        return await cb.answer()
    await state.set_state(RepFind.query)
    await state.update_data(mode=mode)
    await cb.message.edit_text(ui.rep_find_prompt(mode), reply_markup=kb.cancel_rep())
    await cb.answer()


@router.message(RepFind.query, F.text)
async def find_run(message: Message, state: FSMContext):
    me = await db.get_user(message.from_user.id)
    if not me or me["status"] != "accepted":
        return await state.clear()
    mode = (await state.get_data()).get("mode", "vote")
    q = message.text.strip()
    users = [
        u for u in await db.search_users(q, 20)
        if u["status"] == "accepted" and u["tg_id"] != me["tg_id"]
    ][:8]
    if not users:
        return await message.answer(ui.not_found_text(q), reply_markup=kb.cancel_rep())
    await state.clear()
    await message.answer(ui.results_text(q, len(users)), reply_markup=kb.pick_kb(users, mode))


@router.callback_query(F.data.startswith("rep:pick:"))
async def pick(cb: CallbackQuery, state: FSMContext):
    me = await get_member(cb)
    if not me:
        return
    _, _, mode, tid = cb.data.split(":")
    t = await db.get_user(int(tid))
    if not t or t["status"] != "accepted" or t["tg_id"] == me["tg_id"]:
        return await cb.answer("Этого участника нельзя выбрать.", show_alert=True)

    if mode == "vote":
        reason = await db.rep_block_reason(me["tg_id"], t["tg_id"])
        if reason:
            return await cb.answer(reason, show_alert=True)
        await cb.message.edit_text(ui.rep_pick_text(t), reply_markup=kb.vote_kb(t["tg_id"]))
    elif mode == "report":
        if await db.count_open_complaints(me["tg_id"]) >= db.MAX_OPEN_COMPLAINTS:
            return await cb.answer("У тебя уже есть нерассмотренные жалобы. Дождись решения.", show_alert=True)
        await state.set_state(Report.text)
        await state.update_data(tid=t["tg_id"])
        await cb.message.edit_text(ui.report_prompt(t), reply_markup=kb.cancel_rep())
    await cb.answer()


# ---------- голосование ----------

@router.callback_query(F.data.startswith("rep:v:"))
async def vote(cb: CallbackQuery, bot: Bot):
    me = await get_member(cb)
    if not me:
        return
    _, _, sign, tid = cb.data.split(":")
    value = 1 if sign == "p" else -1
    t = await db.get_user(int(tid))
    if not t or t["status"] != "accepted":
        return await cb.answer("Участник недоступен.", show_alert=True)
    reason = await db.rep_block_reason(me["tg_id"], t["tg_id"])
    if reason:
        return await cb.answer(reason, show_alert=True)

    await db.add_rep(me["tg_id"], t["tg_id"], value)
    t = await db.get_user(t["tg_id"])
    try:
        await bot.send_message(t["tg_id"], ui.rep_received_text(me, value))
    except Exception:
        pass
    await cb.message.edit_text(ui.vote_done_text(t, value), reply_markup=kb.back_to_rep())
    await cb.answer("Готово")


# ---------- жалобы ----------

@router.message(Report.text, F.text)
async def report_send(message: Message, state: FSMContext, bot: Bot):
    me = await db.get_user(message.from_user.id)
    data = await state.get_data()
    t = await db.get_user(data.get("tid", 0))
    if not me or me["status"] != "accepted" or not t:
        return await state.clear()

    text = message.text.strip()[:500]
    if not text:
        return await message.answer("Опиши причину текстом.")

    cid = await db.create_complaint(me["tg_id"], t["tg_id"], text)
    try:
        await bot.send_message(
            config.ADMIN_GROUP_ID,
            ui.complaint_card(cid, me, t, text),
            message_thread_id=config.COMPLAINTS_TOPIC_ID,
            reply_markup=kb.complaint_kb(cid),
        )
    except Exception as e:
        log.error("Не удалось отправить жалобу в админ-группу: %s", e)
        await db.close_complaint(cid, "dismissed", 0)
        await state.clear()
        return await message.answer("⚠️ Не удалось отправить жалобу. Попробуй позже.", reply_markup=kb.back_to_rep())

    await state.clear()
    await message.answer(ui.complaint_sent_text(), reply_markup=kb.back_to_rep())


@router.callback_query(F.data.startswith("cmp:"))
async def complaint_decide(cb: CallbackQuery, bot: Bot):
    level = await db.get_level(cb.from_user.id)
    if level < 2:
        return await cb.answer("Нет доступа.", show_alert=True)

    _, action, cid = cb.data.split(":")
    c = await db.get_complaint(int(cid))
    if not c or c["status"] != "pending":
        return await cb.answer("Жалоба уже рассмотрена.", show_alert=True)

    admin = html.escape(cb.from_user.full_name)
    if action == "warn":
        t = await db.get_user(c["target_id"])
        if not t:
            return await cb.answer("Участник не найден.", show_alert=True)
        if t["tg_id"] == cb.from_user.id or level <= roles.level(t["role"]):
            return await cb.answer("Недостаточно прав для варна этому участнику.", show_alert=True)
        await db.apply_action(t["tg_id"], "warn")
        await db.log_action(cb.from_user.id, "warn", t["tg_id"], f"жалоба #{cid}")
        notice = "warn"
        if await db.maybe_autoban(t["tg_id"]):
            await db.log_action(cb.from_user.id, "ban", t["tg_id"], "автобан: 3 варна")
            notice = "ban"
        t = await db.get_user(t["tg_id"])
        try:
            await bot.send_message(t["tg_id"], ui.target_notice(notice, t))
        except Exception:
            pass
        status, mark, warned = "warned", "⚠️ <b>Выдал варн</b>", True
    elif action == "dismiss":
        status, mark, warned = "dismissed", "🗑 <b>Отклонил</b>", False
    else:
        return await cb.answer()

    await db.close_complaint(c["id"], status, cb.from_user.id)
    await cb.message.edit_text(f"{cb.message.html_text}\n\n{mark}: {admin}", reply_markup=None)
    try:
        await bot.send_message(c["from_id"], ui.complaint_result(warned))
    except Exception:
        pass
    await cb.answer("Готово")
