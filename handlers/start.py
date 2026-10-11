from aiogram import Bot, F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import config
import roles
import ui
from database import db
from keyboards.extras import tut_start_kb
from keyboards.main import guest_menu, main_menu

router = Router()


async def home_payload(uid: int):
    """Экран «дом» для любого пользователя: зависит от статуса анкеты."""
    user = await db.get_user(uid)
    status = user["status"]

    # владелец без анкеты сначала заполняет её
    if uid in config.ADMIN_IDS and user["age"] is None and status != "pending":
        return ui.owner_guest_text(), guest_menu()
    if status == "accepted":
        return ui.menu_text(user), main_menu(roles.level(user["role"]))
    if status == "onboarding":
        return ui.tutorial_intro_text(), tut_start_kb()
    if status == "pending":
        return ui.pending_text(), None
    return ui.guest_text(), guest_menu()


@router.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    uid = message.from_user.id
    await db.ensure_user(uid, message.from_user.username)
    await db.fill_staff_defaults(uid, message.from_user.full_name, message.from_user.username)
    text, markup = await home_payload(uid)
    await message.answer(text, reply_markup=markup)


@router.callback_query(F.data.in_({"menu", "home"}))
async def go_home(cb: CallbackQuery, state: FSMContext, bot: Bot):
    """menu — «Назад» внутри разделов (правим текущее сообщение).
    home — кнопка под уведомлениями: присылаем меню новым сообщением, а само уведомление остаётся."""
    await state.clear()
    await db.ensure_user(cb.from_user.id, cb.from_user.username)
    text, markup = await home_payload(cb.from_user.id)
    if cb.data == "menu":
        try:
            await cb.message.edit_text(text, reply_markup=markup)
        except Exception:  # сообщение устарело или не изменилось — присылаем меню заново
            await bot.send_message(cb.from_user.id, text, reply_markup=markup)
    else:
        await bot.send_message(cb.from_user.id, text, reply_markup=markup)
    await cb.answer()
