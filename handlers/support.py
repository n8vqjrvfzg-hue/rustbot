"""Связь с администрацией: пользователь пишет через бота, админы отвечают reply'ем в группе."""
import html
import logging

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, ReactionTypeEmoji

import config
import ui
from database import db
from handlers.common import get_member
from keyboards import support as kb
from keyboards.main import back_kb

router = Router()
log = logging.getLogger(__name__)


class Support(StatesGroup):
    text = State()


# ---------- сторона пользователя ----------

@router.callback_query(F.data == "support")
async def support_start(cb: CallbackQuery, state: FSMContext):
    if not await get_member(cb):
        return
    await state.set_state(Support.text)
    await state.update_data(ticket_id=None)
    await cb.message.edit_text(ui.support_prompt(), reply_markup=kb.cancel_support())
    await cb.answer()


@router.callback_query(F.data.startswith("support:reply:"))
async def support_reply_start(cb: CallbackQuery, state: FSMContext):
    me = await get_member(cb)
    if not me:
        return
    ticket = await db.get_ticket(int(cb.data.split(":")[2]))
    if not ticket or ticket["user_id"] != me["tg_id"] or ticket["status"] != "open":
        return await cb.answer("Обращение закрыто. Создай новое через меню.", show_alert=True)
    await state.set_state(Support.text)
    await state.update_data(ticket_id=ticket["id"])
    await cb.message.answer(ui.support_prompt(reply=True), reply_markup=kb.cancel_support())
    await cb.answer()


@router.message(Support.text, F.text)
async def support_send(message: Message, state: FSMContext, bot: Bot):
    me = await db.get_user(message.from_user.id)
    if not me or me["status"] != "accepted":
        return await state.clear()

    text = message.text.strip()[:1000]
    if not text:
        return await message.answer("Напиши сообщение текстом.")

    ticket_id = (await state.get_data()).get("ticket_id")
    new = ticket_id is None
    if new:
        if await db.count_open_tickets(me["tg_id"]) >= db.MAX_OPEN_TICKETS:
            await state.clear()
            return await message.answer(
                "У тебя уже несколько открытых обращений. Дождись ответа администрации.",
                reply_markup=back_kb(),
            )
        ticket_id = await db.create_ticket(me["tg_id"])
    else:
        ticket = await db.get_ticket(ticket_id)
        if not ticket or ticket["status"] != "open":
            await state.clear()
            return await message.answer("Это обращение уже закрыто. Создай новое через меню.", reply_markup=back_kb())

    try:
        sent = await bot.send_message(
            config.ADMIN_GROUP_ID,
            ui.ticket_card(ticket_id, me, text, new),
            message_thread_id=config.SUPPORT_TOPIC_ID,
            reply_markup=kb.ticket_kb(ticket_id),
        )
    except Exception as e:
        log.error("Не удалось отправить обращение в админ-группу: %s", e)
        if new:
            await db.close_ticket(ticket_id)
        await state.clear()
        return await message.answer("⚠️ Не удалось отправить сообщение. Попробуй позже.", reply_markup=back_kb())

    await db.add_ticket_msg(sent.message_id, ticket_id)
    await state.clear()
    await message.answer(ui.support_sent_text(ticket_id), reply_markup=back_kb())


# ---------- сторона администрации (админ-группа) ----------

@router.message(F.chat.id == config.ADMIN_GROUP_ID, F.reply_to_message)
async def admin_reply(message: Message, bot: Bot):
    ticket = await db.get_ticket_by_msg(message.reply_to_message.message_id)
    if not ticket:
        return  # обычная переписка в группе
    if await db.get_level(message.from_user.id) < 2:
        return
    if not message.text:
        return await message.reply("Пока поддерживаются только текстовые ответы.")
    if ticket["status"] != "open":
        return await message.reply("🔒 Обращение закрыто.")

    try:
        await bot.send_message(
            ticket["user_id"],
            ui.ticket_reply_text(message.text),
            reply_markup=kb.user_reply_kb(ticket["id"]),
        )
    except Exception:
        return await message.reply("⚠️ Не удалось доставить: пользователь заблокировал бота.")

    await db.log_action(message.from_user.id, "ticket_reply", ticket["user_id"], f"#{ticket['id']}")
    try:
        await message.react([ReactionTypeEmoji(emoji="👍")])
    except Exception:
        await message.reply("✅ Отправлено")


@router.callback_query(F.data.startswith("tk:close:"))
async def close_ticket(cb: CallbackQuery, bot: Bot):
    if await db.get_level(cb.from_user.id) < 2:
        return await cb.answer("Нет доступа.", show_alert=True)
    ticket = await db.get_ticket(int(cb.data.split(":")[2]))
    if not ticket or ticket["status"] != "open":
        return await cb.answer("Обращение уже закрыто.", show_alert=True)

    await db.close_ticket(ticket["id"])
    await db.log_action(cb.from_user.id, "ticket_close", ticket["user_id"], f"#{ticket['id']}")
    admin = html.escape(cb.from_user.full_name)
    await cb.message.edit_text(f"{cb.message.html_text}\n\n🔒 <b>Закрыл</b>: {admin}", reply_markup=None)
    try:
        await bot.send_message(ticket["user_id"], ui.ticket_closed_text(ticket["id"]))
    except Exception:
        pass
    await cb.answer("Обращение закрыто")
