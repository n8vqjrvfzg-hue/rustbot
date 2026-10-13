from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

import roles
import timeutil
import ui
from database import db
from handlers.common import get_member
from keyboards.extras import PRIME_PRESETS, grole_kb, prime_kb
from keyboards.profile import notif_kb, profile_kb

router = Router()


class ChangeNick(StatesGroup):
    nick = State()


class ChangePrime(StatesGroup):
    value = State()


async def _profile_text(user) -> str:
    rank = await db.rep_rank(user["tg_id"])
    dlc = (len(await db.user_dlc_ids(user["tg_id"])), len(await db.get_dlc_list()))
    achievements = await db.get_achievements(user["tg_id"])
    is_subscribed = bool(user.get("channel_sub_status"))
    return ui.profile_text(user, rank, dlc, achievements, is_subscribed)


@router.callback_query(F.data == "profile")
async def show_profile(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    user = await get_member(cb)
    if not user:
        return
    await cb.message.edit_text(await _profile_text(user), reply_markup=profile_kb())
    await cb.answer()


@router.callback_query(F.data == "profile:nick")
async def nick_start(cb: CallbackQuery, state: FSMContext):
    if not await get_member(cb):
        return
    await state.set_state(ChangeNick.nick)
    await cb.message.answer(
        f"{ui.header('✏️', 'СМЕНА НИКА')}\n\n"
        "Отправь новый ник (до 32 символов).\n"
        "<i>Для отмены нажми /start</i>"
    )
    await cb.answer()


@router.message(ChangeNick.nick, F.text)
async def nick_save(message: Message, state: FSMContext):
    nick = message.text.strip()
    if not nick or nick.startswith("/"):
        return await message.answer("Отправь ник обычным текстом или нажми /start для отмены.")
    await db.update_nick(message.from_user.id, nick[:32])
    await state.clear()
    user = await db.get_user(message.from_user.id)
    await message.answer("✅ Ник обновлён!\n\n" + await _profile_text(user), reply_markup=profile_kb())


@router.callback_query(F.data == "notif")
async def show_notif(cb: CallbackQuery):
    user = await get_member(cb)
    if not user:
        return
    await cb.message.edit_text(ui.notif_text(), reply_markup=notif_kb(user))
    await cb.answer()


@router.callback_query(F.data.startswith("notif:"))
async def toggle_notif(cb: CallbackQuery):
    if not await get_member(cb):
        return
    key = cb.data.split(":", 1)[1]
    if key not in db.NOTIFY_KEYS:
        return await cb.answer()
    await db.toggle_notify(cb.from_user.id, key)
    user = await db.get_user(cb.from_user.id)
    await cb.message.edit_reply_markup(reply_markup=notif_kb(user))
    await cb.answer("Сохранено")


# ---------- игровые роли ----------

@router.callback_query(F.data == "grole")
async def grole_show(cb: CallbackQuery):
    user = await get_member(cb)
    if not user:
        return
    await cb.message.edit_text(ui.grole_text(user), reply_markup=grole_kb(roles.parse_game_roles(user["game_roles"])))
    await cb.answer()


@router.callback_query(F.data.startswith("grole:"))
async def grole_toggle(cb: CallbackQuery):
    if not await get_member(cb):
        return
    result = await db.toggle_game_role(cb.from_user.id, cb.data.split(":", 1)[1])
    if result == "limit":
        return await cb.answer(f"Можно выбрать не больше {roles.MAX_GAME_ROLES} ролей.", show_alert=True)
    user = await db.get_user(cb.from_user.id)
    await cb.message.edit_text(ui.grole_text(user), reply_markup=grole_kb(roles.parse_game_roles(user["game_roles"])))
    await cb.answer("Сохранено")


# ---------- прайм-тайм ----------

async def _save_prime(target: Message, state: FSMContext, uid: int, value: str) -> None:
    await db.set_prime_time(uid, value)
    await state.clear()
    user = await db.get_user(uid)
    await target.answer("✅ Прайм-тайм обновлён!\n\n" + await _profile_text(user), reply_markup=profile_kb())


@router.callback_query(F.data == "prime")
async def prime_start(cb: CallbackQuery, state: FSMContext):
    if not await get_member(cb):
        return
    await state.set_state(ChangePrime.value)
    await cb.message.answer(ui.prime_prompt(), reply_markup=prime_kb("ptp"))
    await cb.answer()


@router.callback_query(ChangePrime.value, F.data.startswith("ptp:"))
async def prime_pick(cb: CallbackQuery, state: FSMContext):
    value = PRIME_PRESETS.get(cb.data.split(":")[1])
    if not value:
        return await cb.answer()
    await cb.answer()
    await _save_prime(cb.message, state, cb.from_user.id, value)


@router.message(ChangePrime.value, F.text)
async def prime_text(message: Message, state: FSMContext):
    raw = message.text.strip()
    value = timeutil.parse_prime(raw)
    if not value and raw.lower().startswith("гибк"):
        value = PRIME_PRESETS["flex"]
    if not value:
        return await message.answer("⚠️ Не понял время. Напиши в формате <b>19:00-23:00</b> или выбери кнопкой.")
    await _save_prime(message, state, message.from_user.id, value)
