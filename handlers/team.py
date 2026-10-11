"""Поиск команды: заявка уходит в канал, отклики приходят автору в личку."""
import logging

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

import config
import ui
from database import db
from handlers.common import get_member
from keyboards import team as kb
from utils import safe_edit

router = Router()
log = logging.getLogger(__name__)


class TeamNew(StatesGroup):
    text = State()


@router.callback_query(F.data == "team")
async def team_menu(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    if not await get_member(cb):
        return
    await safe_edit(cb.message, ui.team_menu_text(), kb.team_menu_kb())
    await cb.answer()


# ---------- подача заявки ----------

@router.callback_query(F.data == "team:new")
async def team_new(cb: CallbackQuery, state: FSMContext):
    me = await get_member(cb)
    if not me:
        return
    if not config.TEAM_CHANNEL_ID:
        return await cb.answer("Раздел ещё не настроен администрацией.", show_alert=True)
    if await db.count_open_team_requests(me["tg_id"]) >= db.MAX_OPEN_TEAM:
        return await cb.answer(
            f"У тебя уже {db.MAX_OPEN_TEAM} открытые заявки. Закрой одну из них в «Моих заявках».", show_alert=True
        )
    await state.set_state(TeamNew.text)
    await safe_edit(cb.message, ui.team_new_prompt(), kb.cancel_kb())
    await cb.answer()


@router.message(TeamNew.text, F.text)
async def team_post(message: Message, state: FSMContext, bot: Bot):
    me = await db.get_user(message.from_user.id)
    if not me or me["status"] != "accepted":
        return await state.clear()
    text = message.text.strip()[:400]
    if not text:
        return await message.answer("Опиши заявку текстом.")

    rid = await db.create_team_request(me["tg_id"], text)
    post = ui.team_post(rid, me, await db.rep_rank(me["tg_id"]), text)
    try:
        sent = await bot.send_message(config.TEAM_CHANNEL_ID, post, reply_markup=kb.join_kb(rid, 0))
    except Exception as e:
        log.error("Не удалось опубликовать заявку в канале: %s", e)
        await db.close_team_request(rid)
        await state.clear()
        return await message.answer(
            "⚠️ Не удалось опубликовать заявку. Сообщи администрации.", reply_markup=kb.team_menu_kb()
        )
    await db.set_team_post(rid, sent.message_id, post)
    await state.clear()
    await message.answer(ui.team_published_text(rid), reply_markup=kb.team_menu_kb())


# ---------- отклик «Я готов» (кнопка под постом в канале) ----------

@router.callback_query(F.data.startswith("team:join:"))
async def team_join(cb: CallbackQuery, bot: Bot):
    me = await get_member(cb)
    if not me:
        return
    req = await db.get_team_request(int(cb.data.split(":")[2]))
    if not req or req["status"] != "open":
        return await cb.answer("Набор уже закрыт.", show_alert=True)
    if req["user_id"] == me["tg_id"]:
        return await cb.answer("Это твоя собственная заявка.", show_alert=True)
    if not await db.add_team_response(req["id"], me["tg_id"]):
        return await cb.answer("Ты уже откликнулся на эту заявку.", show_alert=True)

    n = await db.team_response_count(req["id"])
    try:
        await cb.message.edit_reply_markup(reply_markup=kb.join_kb(req["id"], n))
    except Exception:
        pass

    author = await db.get_user(req["user_id"])
    if author and author["notify_team"]:
        try:
            await bot.send_message(
                author["tg_id"],
                ui.team_response_card(req, me, await db.rep_rank(me["tg_id"])),
                reply_markup=kb.contact_kb(me),
            )
        except Exception:
            pass
    if author:
        try:
            await bot.send_message(
                me["tg_id"],
                ui.team_joined_text(req, author, await db.rep_rank(author["tg_id"])),
                reply_markup=kb.contact_kb(author),
            )
        except Exception:
            pass
    await cb.answer("✅ Отклик отправлен! Автор получил уведомление.", show_alert=True)


# ---------- мои заявки ----------

async def _show_my(cb: CallbackQuery, uid: int) -> None:
    reqs = await db.my_team_requests(uid)
    counts = {r["id"]: await db.team_response_count(r["id"]) for r in reqs}
    await safe_edit(cb.message, ui.team_my_text(len(reqs)), kb.my_requests_kb(reqs, counts))


@router.callback_query(F.data == "team:my")
async def team_my(cb: CallbackQuery):
    if not await get_member(cb):
        return
    await _show_my(cb, cb.from_user.id)
    await cb.answer()


@router.callback_query(F.data.startswith("team:view:"))
async def team_view(cb: CallbackQuery):
    me = await get_member(cb)
    if not me:
        return
    req = await db.get_team_request(int(cb.data.split(":")[2]))
    if not req or req["user_id"] != me["tg_id"]:
        return await cb.answer("Заявка не найдена.", show_alert=True)
    responders = await db.team_responders(req["id"])
    n = await db.team_response_count(req["id"])
    await safe_edit(cb.message, ui.team_request_view(req, n, responders), kb.request_view_kb(req["id"], responders))
    await cb.answer()


@router.callback_query(F.data.startswith("team:close:"))
async def team_close(cb: CallbackQuery, bot: Bot):
    me = await get_member(cb)
    if not me:
        return
    req = await db.get_team_request(int(cb.data.split(":")[2]))
    if not req or req["user_id"] != me["tg_id"]:
        return await cb.answer("Заявка не найдена.", show_alert=True)
    await db.close_team_request(req["id"])
    if req["channel_msg_id"] and config.TEAM_CHANNEL_ID:
        try:
            await bot.edit_message_text(
                (req["post_text"] or "") + "\n\n🔒 <b>Набор закрыт</b>",
                chat_id=config.TEAM_CHANNEL_ID,
                message_id=req["channel_msg_id"],
                reply_markup=None,
            )
        except Exception as e:
            log.warning("Не удалось обновить пост в канале: %s", e)
    await _show_my(cb, me["tg_id"])
    await cb.answer("Набор закрыт")
