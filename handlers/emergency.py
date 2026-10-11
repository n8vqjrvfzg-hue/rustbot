"""Экстренный сбор: админ пишет текст, бот рассылает его всем."""
from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

import ui
from database import db
from handlers.common import get_member, need_level
from keyboards import extras as kb
from utils import safe_edit, start_broadcast

router = Router()
MIN_LEVEL = 2  # администратор и выше


class EmergencyNew(StatesGroup):
    text = State()
    confirm = State()


@router.callback_query(F.data == "adm:em")
async def em_start(cb: CallbackQuery, state: FSMContext):
    if await need_level(cb, MIN_LEVEL) is None:
        return
    await state.set_state(EmergencyNew.text)
    await safe_edit(cb.message, ui.emergency_prompt(), kb.em_cancel_kb())
    await cb.answer()


@router.message(EmergencyNew.text, F.text)
async def em_text(message: Message, state: FSMContext):
    if await db.get_level(message.from_user.id) < MIN_LEVEL:
        return await state.clear()
    text = message.text.strip()[:500]
    if not text:
        return await message.answer("Напиши текст сбора.")
    await state.update_data(text=text)
    await state.set_state(EmergencyNew.confirm)
    me = await db.get_user(message.from_user.id)
    await message.answer(ui.emergency_preview(text, me), reply_markup=kb.em_confirm_kb())


@router.callback_query(EmergencyNew.confirm, F.data == "adm:em:pub")
async def em_publish(cb: CallbackQuery, state: FSMContext, bot: Bot):
    if await need_level(cb, MIN_LEVEL) is None:
        return
    if await db.recent_emergency(2):
        return await cb.answer("Экстренный сбор уже был минуту назад. Подожди пару минут.", show_alert=True)

    data = await state.get_data()
    await state.clear()
    me = await db.get_user(cb.from_user.id)
    eid = await db.create_emergency(data["text"], cb.from_user.id)
    await db.log_action(cb.from_user.id, "emergency_send", None, f"#{eid}")

    start_broadcast(
        bot, await db.recipients("emergency"), ui.emergency_message(data["text"], me),
        kb.em_ack_kb(eid), report_to=cb.from_user.id,
    )
    e = await db.get_emergency(eid)
    await safe_edit(
        cb.message,
        "🚨 <b>Сбор разослан!</b>\n\n" + ui.emergency_card(e, 0, []),
        kb.em_card_kb(eid),
    )
    await cb.answer()


@router.callback_query(F.data.startswith("adm:em:view:"))
async def em_view(cb: CallbackQuery):
    if await need_level(cb, MIN_LEVEL) is None:
        return
    e = await db.get_emergency(int(cb.data.split(":")[3]))
    if not e:
        return await cb.answer("Сбор не найден.", show_alert=True)
    text = ui.emergency_card(e, await db.emergency_ack_count(e["id"]), await db.emergency_ack_names(e["id"]))
    await safe_edit(cb.message, text, kb.em_card_kb(e["id"]))
    await cb.answer("Обновлено")


# ---------- сторона участника ----------

@router.callback_query(F.data.startswith("em:ack:"))
async def em_ack(cb: CallbackQuery):
    me = await get_member(cb)
    if not me:
        return
    eid = int(cb.data.split(":")[2])
    if not await db.get_emergency(eid):
        return await cb.answer("Сбор не найден.", show_alert=True)
    await db.ack_emergency(eid, me["tg_id"])
    try:
        await cb.message.edit_reply_markup(reply_markup=kb.em_acked_kb())
    except Exception:
        pass
    await cb.answer("✅ Отмечено! Админы увидят, что ты идёшь.")


@router.callback_query(F.data == "em:noop")
async def em_noop(cb: CallbackQuery):
    await cb.answer()
