import html
import logging

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

import config
import timeutil
import ui
from database import db
from keyboards.extras import PRIME_PRESETS, prime_kb, tut_start_kb
from keyboards.main import decision_kb, main_menu

router = Router()
log = logging.getLogger(__name__)


class Anketa(StatesGroup):
    name = State()
    nick = State()
    age = State()
    hours = State()
    prime = State()
    about = State()


@router.callback_query(F.data == "apply")
async def apply_start(cb: CallbackQuery, state: FSMContext):
    await db.ensure_user(cb.from_user.id, cb.from_user.username)
    user = await db.get_user(cb.from_user.id)
    owner_needs = cb.from_user.id in config.ADMIN_IDS and user["age"] is None

    if user["status"] == "pending":
        return await cb.answer("Анкета уже на рассмотрении.", show_alert=True)
    if user["status"] == "onboarding":
        return await cb.answer("Анкета принята. Пройди обучение: нажми /start.", show_alert=True)
    if user["status"] == "accepted" and not owner_needs:
        return await cb.answer("Анкета уже принята.", show_alert=True)
    if not owner_needs and await db.get_setting("apps_open", "1") != "1":
        return await cb.answer("Приём анкет временно закрыт.", show_alert=True)

    await state.set_state(Anketa.name)
    await cb.message.answer(ui.anketa_question(1))
    await cb.answer()


@router.message(Anketa.name, F.text)
async def q_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip()[:64])
    await state.set_state(Anketa.nick)
    await message.answer(ui.anketa_question(2))


@router.message(Anketa.nick, F.text)
async def q_nick(message: Message, state: FSMContext):
    await state.update_data(nick=message.text.strip()[:64])
    await state.set_state(Anketa.age)
    await message.answer(ui.anketa_question(3))


@router.message(Anketa.age, F.text)
async def q_age(message: Message, state: FSMContext):
    if not message.text.isdigit() or not (5 <= int(message.text) <= 99):
        return await message.answer("⚠️ Введи возраст числом, например <b>18</b>.")
    await state.update_data(age=int(message.text))
    await state.set_state(Anketa.hours)
    await message.answer(ui.anketa_question(4))


@router.message(Anketa.hours, F.text)
async def q_hours(message: Message, state: FSMContext):
    if not message.text.isdigit() or int(message.text) > 100000:
        return await message.answer("⚠️ Введи количество часов числом, например <b>500</b>.")
    await state.update_data(hours=int(message.text))
    await state.set_state(Anketa.prime)
    await message.answer(ui.anketa_question(5), reply_markup=prime_kb("pt"))


async def _prime_done(target: Message, state: FSMContext, value: str):
    await state.update_data(prime=value)
    await state.set_state(Anketa.about)
    await target.answer(ui.anketa_question(6))


@router.callback_query(Anketa.prime, F.data.startswith("pt:"))
async def q_prime_button(cb: CallbackQuery, state: FSMContext):
    value = PRIME_PRESETS.get(cb.data.split(":")[1])
    if not value:
        return await cb.answer()
    await cb.answer()
    await _prime_done(cb.message, state, value)


@router.message(Anketa.prime, F.text)
async def q_prime_text(message: Message, state: FSMContext):
    raw = message.text.strip()
    value = timeutil.parse_prime(raw)
    if not value and raw.lower().startswith("гибк"):
        value = PRIME_PRESETS["flex"]
    if not value:
        return await message.answer(
            "⚠️ Не понял время. Напиши в формате <b>19:00-23:00</b> или выбери вариант кнопкой."
        )
    await _prime_done(message, state, value)


@router.message(Anketa.about, F.text)
async def q_about(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    await state.clear()
    about = message.text.strip()[:500]
    uid = message.from_user.id

    current = await db.get_user(uid)
    if current and current["status"] == "pending" and uid not in config.ADMIN_IDS:
        return await message.answer(ui.pending_text())

    app_id = await db.create_application(
        uid, data["name"], data["nick"], data["age"], data["hours"], data["prime"], about
    )
    card = ui.application_card(app_id, message.from_user, data, about)

    # владелец принимается автоматически и сразу получает полный доступ
    if uid in config.ADMIN_IDS:
        await db.decide_application(app_id, True, uid, accept_status="accepted")
        try:
            await bot.send_message(
                config.ADMIN_GROUP_ID, card + "\n\n✅ <b>Принято автоматически (владелец)</b>",
                message_thread_id=config.APPLICATIONS_TOPIC_ID,
            )
        except Exception as e:
            log.warning("Не удалось отправить карточку владельца в админ-группу: %s", e)
        level = await db.get_level(uid)
        await message.answer(ui.owner_accepted_text(), reply_markup=main_menu(level))
        return

    try:
        await bot.send_message(
            config.ADMIN_GROUP_ID, card,
            message_thread_id=config.APPLICATIONS_TOPIC_ID,
            reply_markup=decision_kb(app_id),
        )
    except Exception as e:
        log.error("Не удалось отправить анкету в админ-группу: %s", e)
        await db.cancel_application(app_id, uid)
        return await message.answer("⚠️ Не удалось передать анкету администрации. Попробуй чуть позже.")
    await message.answer(ui.anketa_sent_text())


@router.callback_query(F.data.startswith("app:"))
async def decide(cb: CallbackQuery, bot: Bot):
    if await db.get_level(cb.from_user.id) < 2:
        return await cb.answer("Нет доступа.", show_alert=True)

    _, action, app_id = cb.data.split(":")
    app = await db.get_application(int(app_id))
    if not app or app["status"] != "pending":
        return await cb.answer("Анкета уже обработана.", show_alert=True)

    accepted = action == "accept"
    await db.decide_application(app["id"], accepted, cb.from_user.id)
    await db.log_action(cb.from_user.id, "app_accept" if accepted else "app_reject", app["user_id"])

    mark = "✅ <b>Принял</b>" if accepted else "❌ <b>Отклонил</b>"
    admin = html.escape(cb.from_user.full_name)
    await cb.message.edit_text(f"{cb.message.html_text}\n\n{mark}: {admin}", reply_markup=None)

    try:
        if accepted:
            await bot.send_message(app["user_id"], ui.accepted_text(), reply_markup=tut_start_kb())
        else:
            await bot.send_message(app["user_id"], ui.rejected_text())
    except Exception:
        pass  # пользователь мог заблокировать бота
    await cb.answer("Готово")
