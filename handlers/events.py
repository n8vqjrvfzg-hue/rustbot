"""Мероприятия: календарь для участников, создание и удаление для админов."""
from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

import timeutil
import ui
from database import db
from handlers.common import get_member, need_level
from keyboards import events as kb
from utils import safe_edit, start_broadcast

router = Router()
MIN_LEVEL = 2  # администратор и выше


class EventNew(StatesGroup):
    title = State()
    desc = State()
    when = State()
    place = State()
    confirm = State()


# ---------- участники: календарь ----------

async def _show_calendar(cb: CallbackQuery, year: int, month: int) -> None:
    start, end = timeutil.month_bounds(year, month)
    events = await db.events_between(start, end)
    await safe_edit(cb.message, ui.calendar_screen(year, month, len(events)), kb.calendar_kb(year, month, events))


@router.callback_query(F.data == "events")
async def events_home(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    if not await get_member(cb):
        return
    now = timeutil.local_now()
    await _show_calendar(cb, now.year, now.month)
    await cb.answer()


@router.callback_query(F.data.startswith("ev:cal:"))
async def events_month(cb: CallbackQuery):
    if not await get_member(cb):
        return
    try:
        year, month = (int(x) for x in cb.data.split(":")[2].split("-"))
    except ValueError:
        return await cb.answer()
    if not (1 <= month <= 12 and 2020 <= year <= 2100):
        return await cb.answer()
    await _show_calendar(cb, year, month)
    await cb.answer()


async def _event_view(e, uid: int):
    going_n = await db.rsvp_count(e["id"])
    names = await db.rsvp_names(e["id"])
    i_go = await db.is_going(e["id"], uid)
    d = timeutil.to_local(e["starts_at"])
    return ui.event_card(e, going_n, names, i_go), kb.event_kb(e["id"], i_go, f"{d.year}-{d.month:02d}")


@router.callback_query(F.data.startswith("ev:open:"))
async def event_open(cb: CallbackQuery):
    me = await get_member(cb)
    if not me:
        return
    e = await db.get_event(int(cb.data.split(":")[2]))
    if not e:
        return await cb.answer("Мероприятие не найдено или отменено.", show_alert=True)
    text, markup = await _event_view(e, me["tg_id"])
    await safe_edit(cb.message, text, markup)
    await cb.answer()


@router.callback_query(F.data.startswith("ev:go:"))
async def event_go(cb: CallbackQuery):
    me = await get_member(cb)
    if not me:
        return
    e = await db.get_event(int(cb.data.split(":")[2]))
    if not e:
        return await cb.answer("Мероприятие не найдено или отменено.", show_alert=True)
    if e["starts_at"] <= timeutil.now_str():
        return await cb.answer("Мероприятие уже началось.", show_alert=True)
    going = await db.toggle_rsvp(e["id"], me["tg_id"])
    text, markup = await _event_view(e, me["tg_id"])
    await safe_edit(cb.message, text, markup)
    await cb.answer("✅ Записал тебя!" if going else "Запись отменена")


# ---------- админ: меню и создание ----------

@router.callback_query(F.data == "adm:events")
async def admin_menu(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    if await need_level(cb, MIN_LEVEL) is None:
        return
    await safe_edit(cb.message, ui.events_admin_text(), kb.events_admin_kb())
    await cb.answer()


@router.callback_query(F.data == "adm:ev:new")
async def new_start(cb: CallbackQuery, state: FSMContext):
    if await need_level(cb, MIN_LEVEL) is None:
        return
    await state.set_state(EventNew.title)
    await safe_edit(cb.message, ui.event_new_prompt(1), kb.cancel_kb())
    await cb.answer()


async def _staff(message: Message, state: FSMContext) -> bool:
    if await db.get_level(message.from_user.id) < MIN_LEVEL:
        await state.clear()
        return False
    return True


@router.message(EventNew.title, F.text)
async def new_title(message: Message, state: FSMContext):
    if not await _staff(message, state):
        return
    await state.update_data(title=message.text.strip()[:100])
    await state.set_state(EventNew.desc)
    await message.answer(ui.event_new_prompt(2), reply_markup=kb.cancel_kb())


@router.message(EventNew.desc, F.text)
async def new_desc(message: Message, state: FSMContext):
    if not await _staff(message, state):
        return
    await state.update_data(desc=message.text.strip()[:800])
    await state.set_state(EventNew.when)
    await message.answer(ui.event_new_prompt(3), reply_markup=kb.cancel_kb())


@router.message(EventNew.when, F.text)
async def new_when(message: Message, state: FSMContext):
    if not await _staff(message, state):
        return
    starts = timeutil.parse_local(message.text)
    if not starts:
        return await message.answer("⚠️ Не понял дату. Формат: <b>ДД.ММ.ГГГГ ЧЧ:ММ</b>, например 12.10.2026 20:00")
    if starts <= timeutil.now_str():
        return await message.answer("⚠️ Эта дата уже прошла. Укажи время в будущем.")
    await state.update_data(starts_at=starts)
    await state.set_state(EventNew.place)
    await message.answer(ui.event_new_prompt(4), reply_markup=kb.cancel_kb())


@router.message(EventNew.place, F.text)
async def new_place(message: Message, state: FSMContext):
    if not await _staff(message, state):
        return
    raw = message.text.strip()
    place = None if raw in ("-", "—") else raw[:100]
    await state.update_data(place=place)
    data = await state.get_data()
    preview = {
        "title": data["title"], "description": data["desc"],
        "place": place, "starts_at": data["starts_at"],
    }
    await state.set_state(EventNew.confirm)
    await message.answer(ui.event_preview(preview), reply_markup=kb.publish_kb())


@router.callback_query(EventNew.confirm, F.data == "adm:ev:pub")
async def publish(cb: CallbackQuery, state: FSMContext, bot: Bot):
    if await need_level(cb, MIN_LEVEL) is None:
        return
    data = await state.get_data()
    await state.clear()
    eid = await db.create_event(data["title"], data["desc"], data["place"], data["starts_at"], cb.from_user.id)
    await db.log_action(cb.from_user.id, "event_create", None, f"#{eid}")
    e = await db.get_event(eid)
    start_broadcast(
        bot, await db.recipients("events"), ui.event_announce(e), kb.announce_kb(eid), report_to=cb.from_user.id
    )
    await safe_edit(
        cb.message,
        "✅ <b>Мероприятие опубликовано!</b> Рассылка запущена.\n\n" + ui.event_card(e, 0, [], None),
        kb.admin_event_kb(eid),
    )
    await cb.answer()


@router.callback_query(EventNew.confirm, F.data == "adm:ev:cancel")
async def publish_cancel(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    if await need_level(cb, MIN_LEVEL) is None:
        return
    await safe_edit(cb.message, ui.events_admin_text(), kb.events_admin_kb())
    await cb.answer("Отменено")


# ---------- админ: список, просмотр, удаление ----------

@router.callback_query(F.data == "adm:ev:list")
async def admin_list(cb: CallbackQuery):
    if await need_level(cb, MIN_LEVEL) is None:
        return
    events = await db.upcoming_events(10)
    text = f"{ui.header('📋', 'БЛИЖАЙШИЕ МЕРОПРИЯТИЯ')}\n\n" + ("Выбери мероприятие 👇" if events else "Мероприятий пока нет.")
    await safe_edit(cb.message, text, kb.admin_list_kb(events))
    await cb.answer()


@router.callback_query(F.data.startswith("adm:ev:view:"))
async def admin_view(cb: CallbackQuery):
    if await need_level(cb, MIN_LEVEL) is None:
        return
    e = await db.get_event(int(cb.data.split(":")[3]))
    if not e:
        return await cb.answer("Мероприятие не найдено.", show_alert=True)
    text = ui.event_card(e, await db.rsvp_count(e["id"]), await db.rsvp_names(e["id"]), None)
    await safe_edit(cb.message, text, kb.admin_event_kb(e["id"]))
    await cb.answer()


@router.callback_query(F.data.startswith("adm:ev:ask:"))
async def admin_ask_delete(cb: CallbackQuery):
    if await need_level(cb, MIN_LEVEL) is None:
        return
    e = await db.get_event(int(cb.data.split(":")[3]))
    if not e:
        return await cb.answer("Мероприятие не найдено.", show_alert=True)
    await safe_edit(cb.message, ui.event_delete_confirm(e), kb.confirm_delete_kb(e["id"]))
    await cb.answer()


@router.callback_query(F.data.startswith("adm:ev:del:"))
async def admin_delete(cb: CallbackQuery, bot: Bot):
    if await need_level(cb, MIN_LEVEL) is None:
        return
    e = await db.get_event(int(cb.data.split(":")[3]))
    if not e:
        return await cb.answer("Мероприятие не найдено.", show_alert=True)
    going = await db.rsvp_user_ids(e["id"], only_notify=True)
    await db.delete_event(e["id"])
    await db.log_action(cb.from_user.id, "event_delete", None, f"#{e['id']} {e['title']}")
    start_broadcast(bot, going, ui.event_cancelled(e["title"]))
    events = await db.upcoming_events(10)
    text = f"{ui.header('📋', 'БЛИЖАЙШИЕ МЕРОПРИЯТИЯ')}\n\n🗑 Мероприятие удалено.\n\n" + ("Выбери мероприятие 👇" if events else "Мероприятий пока нет.")
    await safe_edit(cb.message, text, kb.admin_list_kb(events))
    await cb.answer("Удалено")


# ---------- календарь: нажатия на дни ----------

@router.callback_query(F.data.startswith("ev:day:"))
async def event_day(cb: CallbackQuery):
    me = await get_member(cb)
    if not me:
        return
    try:
        year, month, day = (int(x) for x in cb.data.split(":")[2].split("-"))
        start, end = timeutil.day_bounds(year, month, day)
    except ValueError:
        return await cb.answer()
    events = await db.events_between(start, end)
    if not events:
        return await cb.answer("В этот день мероприятий нет.")
    if len(events) == 1:
        text, markup = await _event_view(events[0], me["tg_id"])
        await safe_edit(cb.message, text, markup)
        return await cb.answer()
    await safe_edit(cb.message, ui.day_text(year, month, day, len(events)), kb.day_kb(events, year, month))
    await cb.answer()


@router.callback_query(F.data == "ev:noday")
async def event_noday(cb: CallbackQuery):
    await cb.answer("В этот день мероприятий нет.")


@router.callback_query(F.data == "ev:noop")
async def event_noop(cb: CallbackQuery):
    await cb.answer()
