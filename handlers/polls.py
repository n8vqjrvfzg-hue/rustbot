"""Голосования: участники голосуют, модераторы и выше создают и управляют."""
from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

import timeutil
import ui
from database import db
from handlers.common import get_member, need_level
from keyboards import polls as kb
from utils import safe_edit, start_broadcast

router = Router()
MIN_LEVEL = 1  # модератор и выше


class PollNew(StatesGroup):
    question = State()
    options = State()
    duration = State()


async def _user_view(poll, uid: int):
    options = db.poll_options(poll)
    counts = await db.poll_counts(poll["id"])
    my = await db.get_vote(poll["id"], uid)
    is_open = db.poll_is_open(poll)
    show = my is not None or not is_open
    return ui.poll_text(poll, options, counts, my, show, is_open), kb.poll_kb(poll["id"], options, is_open and my is None)


async def _admin_view(poll, uid: int):
    options = db.poll_options(poll)
    counts = await db.poll_counts(poll["id"])
    my = await db.get_vote(poll["id"], uid)
    is_open = db.poll_is_open(poll)
    return ui.poll_text(poll, options, counts, my, True, is_open), kb.admin_poll_kb(poll["id"], is_open)


# ---------- участники ----------

@router.callback_query(F.data == "polls")
async def polls_list(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    me = await get_member(cb)
    if not me:
        return
    polls = await db.active_polls(10)
    voted = {p["id"] for p in polls if await db.get_vote(p["id"], me["tg_id"]) is not None}
    await safe_edit(cb.message, ui.polls_list_text(len(polls)), kb.polls_list_kb(polls, voted))
    await cb.answer()


@router.callback_query(F.data.startswith("pl:open:"))
async def poll_open(cb: CallbackQuery):
    me = await get_member(cb)
    if not me:
        return
    poll = await db.get_poll(int(cb.data.split(":")[2]))
    if not poll:
        return await cb.answer("Голосование не найдено.", show_alert=True)
    text, markup = await _user_view(poll, me["tg_id"])
    await safe_edit(cb.message, text, markup)
    await cb.answer()


@router.callback_query(F.data.startswith("pl:v:"))
async def poll_vote(cb: CallbackQuery):
    me = await get_member(cb)
    if not me:
        return
    _, _, pid, idx = cb.data.split(":")
    poll = await db.get_poll(int(pid))
    if not poll or not db.poll_is_open(poll):
        return await cb.answer("Голосование уже завершено.", show_alert=True)
    if not 0 <= int(idx) < len(db.poll_options(poll)):
        return await cb.answer()
    if not await db.add_vote(poll["id"], me["tg_id"], int(idx)):
        return await cb.answer("Ты уже проголосовал.", show_alert=True)
    text, markup = await _user_view(poll, me["tg_id"])
    await safe_edit(cb.message, text, markup)
    await cb.answer("✅ Голос принят")


# ---------- админ: меню и создание ----------

@router.callback_query(F.data == "adm:polls")
async def admin_menu(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    if await need_level(cb, MIN_LEVEL) is None:
        return
    await safe_edit(cb.message, ui.polls_admin_text(), kb.polls_admin_kb())
    await cb.answer()


@router.callback_query(F.data == "adm:pl:new")
async def new_start(cb: CallbackQuery, state: FSMContext):
    if await need_level(cb, MIN_LEVEL) is None:
        return
    await state.set_state(PollNew.question)
    await safe_edit(cb.message, ui.poll_new_question(), kb.cancel_kb())
    await cb.answer()


@router.message(PollNew.question, F.text)
async def new_question(message: Message, state: FSMContext):
    if await db.get_level(message.from_user.id) < MIN_LEVEL:
        return await state.clear()
    await state.update_data(question=message.text.strip()[:200])
    await state.set_state(PollNew.options)
    await message.answer(ui.poll_new_options(), reply_markup=kb.cancel_kb())


@router.message(PollNew.options, F.text)
async def new_options(message: Message, state: FSMContext):
    if await db.get_level(message.from_user.id) < MIN_LEVEL:
        return await state.clear()
    opts = [line.strip()[:60] for line in message.text.splitlines() if line.strip()]
    if not 2 <= len(opts) <= 6:
        return await message.answer("⚠️ Нужно от 2 до 6 вариантов, каждый с новой строки.")
    await state.update_data(options=opts)
    await state.set_state(PollNew.duration)
    await message.answer(ui.poll_duration_prompt(), reply_markup=kb.duration_kb())


@router.callback_query(PollNew.duration, F.data.startswith("adm:pl:dur:"))
async def new_duration(cb: CallbackQuery, state: FSMContext, bot: Bot):
    if await need_level(cb, MIN_LEVEL) is None:
        return
    days = int(cb.data.split(":")[3])
    data = await state.get_data()
    await state.clear()

    ends = timeutil.in_days(days) if days > 0 else None
    pid = await db.create_poll(data["question"], data["options"], ends, cb.from_user.id)
    await db.log_action(cb.from_user.id, "poll_create", None, f"#{pid}")

    poll = await db.get_poll(pid)
    start_broadcast(
        bot, await db.recipients("votes"), ui.poll_announce(poll), kb.announce_kb(pid), report_to=cb.from_user.id
    )
    text, markup = await _admin_view(poll, cb.from_user.id)
    await safe_edit(cb.message, "✅ <b>Голосование опубликовано!</b> Рассылка запущена.\n\n" + text, markup)
    await cb.answer()


# ---------- админ: список, просмотр, завершение, удаление ----------

@router.callback_query(F.data == "adm:pl:list")
async def admin_list(cb: CallbackQuery):
    if await need_level(cb, MIN_LEVEL) is None:
        return
    polls = await db.recent_polls(10)
    text = f"{ui.header('📋', 'ВСЕ ГОЛОСОВАНИЯ')}\n\n" + ("Последние 10 👇" if polls else "Голосований пока нет.")
    await safe_edit(cb.message, text, kb.admin_list_kb(polls))
    await cb.answer()


@router.callback_query(F.data.startswith("adm:pl:view:"))
async def admin_view(cb: CallbackQuery):
    if await need_level(cb, MIN_LEVEL) is None:
        return
    poll = await db.get_poll(int(cb.data.split(":")[3]))
    if not poll:
        return await cb.answer("Голосование не найдено.", show_alert=True)
    text, markup = await _admin_view(poll, cb.from_user.id)
    await safe_edit(cb.message, text, markup)
    await cb.answer()


@router.callback_query(F.data.startswith("adm:pl:close:"))
async def admin_close(cb: CallbackQuery):
    if await need_level(cb, MIN_LEVEL) is None:
        return
    poll = await db.get_poll(int(cb.data.split(":")[3]))
    if not poll:
        return await cb.answer("Голосование не найдено.", show_alert=True)
    await db.close_poll(poll["id"])
    await db.log_action(cb.from_user.id, "poll_close", None, f"#{poll['id']}")
    poll = await db.get_poll(poll["id"])
    text, markup = await _admin_view(poll, cb.from_user.id)
    await safe_edit(cb.message, text, markup)
    await cb.answer("Голосование завершено")


@router.callback_query(F.data.startswith("adm:pl:ask:"))
async def admin_ask_delete(cb: CallbackQuery):
    if await need_level(cb, MIN_LEVEL) is None:
        return
    poll = await db.get_poll(int(cb.data.split(":")[3]))
    if not poll:
        return await cb.answer("Голосование не найдено.", show_alert=True)
    await safe_edit(cb.message, ui.poll_delete_confirm(poll), kb.confirm_delete_kb(poll["id"]))
    await cb.answer()


@router.callback_query(F.data.startswith("adm:pl:del:"))
async def admin_delete(cb: CallbackQuery):
    if await need_level(cb, MIN_LEVEL) is None:
        return
    pid = int(cb.data.split(":")[3])
    await db.delete_poll(pid)
    await db.log_action(cb.from_user.id, "poll_delete", None, f"#{pid}")
    polls = await db.recent_polls(10)
    text = f"{ui.header('📋', 'ВСЕ ГОЛОСОВАНИЯ')}\n\n🗑 Голосование удалено.\n\n" + ("Последние 10 👇" if polls else "Голосований пока нет.")
    await safe_edit(cb.message, text, kb.admin_list_kb(polls))
    await cb.answer("Удалено")
