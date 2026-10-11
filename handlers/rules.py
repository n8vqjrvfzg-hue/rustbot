"""Правила сообщества: просмотр участниками, подтверждение после обучения, редактирование админами."""
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

import roles
import ui
from database import db
from handlers.common import need_level
from keyboards import extras as kb
from keyboards.main import main_menu
from utils import safe_edit

router = Router()
MIN_LEVEL = 3  # как и вся вкладка «Настройки»: заместитель и выше


class RulesEdit(StatesGroup):
    text = State()


# ---------- участники ----------

@router.callback_query(F.data == "rules")
async def rules_open(cb: CallbackQuery):
    """Кнопка «Правила» в главном меню (для новичка на последнем шаге — с кнопкой согласия)."""
    user = await db.get_user(cb.from_user.id)
    status = user["status"] if user else None
    if status not in ("accepted", "rules"):
        return await cb.answer("Правила откроются после одобрения анкеты.", show_alert=True)
    first_time = status == "rules"
    text = ui.rules_screen(await db.get_rules_custom(), first_time=first_time)
    await safe_edit(cb.message, text, kb.rules_ok_kb() if first_time else kb.rules_view_kb())
    await cb.answer()


@router.callback_query(F.data == "rules:ok")
async def rules_ok(cb: CallbackQuery):
    """Новичок подтвердил правила: теперь он полноценный участник."""
    user = await db.get_user(cb.from_user.id)
    if user and user["status"] == "accepted":
        return await cb.answer("Правила уже приняты ✅")
    if not await db.accept_rules(cb.from_user.id):
        return await cb.answer("Эта кнопка пока недоступна. Нажми /start.", show_alert=True)
    await safe_edit(cb.message, ui.tutorial_done_text(), main_menu(roles.level(user["role"])))
    await cb.answer("🎓 Добро пожаловать!")


# ---------- админы (Настройки → Правила) ----------

async def _render_admin(cb: CallbackQuery) -> None:
    await safe_edit(cb.message, ui.rules_admin_text(await db.get_rules_custom()), kb.rules_admin_kb())


@router.callback_query(F.data == "adm:rules")
async def admin_home(cb: CallbackQuery, state: FSMContext):
    if await need_level(cb, MIN_LEVEL) is None:
        return
    await state.clear()
    await _render_admin(cb)
    await cb.answer()


@router.callback_query(F.data == "adm:rules:edit")
async def admin_edit(cb: CallbackQuery, state: FSMContext):
    if await need_level(cb, MIN_LEVEL) is None:
        return
    await state.set_state(RulesEdit.text)
    await safe_edit(cb.message, ui.rules_edit_prompt(), kb.rules_cancel_kb())
    await cb.answer()


@router.message(RulesEdit.text, F.text)
async def admin_save(message: Message, state: FSMContext):
    if await db.get_level(message.from_user.id) < MIN_LEVEL:
        return await state.clear()
    text = message.html_text.strip()  # сохраняем форматирование, заданное в Telegram
    if len(text) < 20:
        return await message.answer("⚠️ Слишком коротко. Напиши правила подробнее.")
    if len(text) > ui.RULES_MAX_LEN:
        return await message.answer(
            f"⚠️ Слишком длинно: {len(text)} из {ui.RULES_MAX_LEN} символов. Сократи текст и отправь снова."
        )
    await db.set_rules_custom(text)
    await db.log_action(message.from_user.id, "setting", None, "rules_text")
    await state.clear()
    await message.answer(ui.rules_saved_text(), reply_markup=kb.rules_admin_kb())
