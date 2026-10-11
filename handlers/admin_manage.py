"""Админ-меню: управление участниками и ролями."""
from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

import roles
import ui
from database import db
from keyboards import admin as kb

router = Router()
PAGE = 8


class Find(StatesGroup):
    query = State()


class EditField(StatesGroup):
    value = State()


# ---------- вспомогательное ----------

async def _safe_edit(msg: Message, text: str, markup) -> None:
    try:
        await msg.edit_text(text, reply_markup=markup)
    except TelegramBadRequest as e:
        if "not modified" not in str(e):
            raise


async def _need_staff(cb: CallbackQuery) -> int | None:
    level = await db.get_level(cb.from_user.id)
    if level < 2:
        await cb.answer("Нет доступа.", show_alert=True)
        return None
    return level


def _can_act(level: int, viewer_id: int, target) -> bool:
    return (
        target is not None
        and target["tg_id"] != viewer_id
        and level >= 2
        and level > roles.level(target["role"])
    )


async def _target(cb: CallbackQuery, tid: int):
    t = await db.get_user(tid)
    if not t:
        await cb.answer("Участник не найден.", show_alert=True)
    return t


async def _notify(bot: Bot, tg_id: int, text: str) -> None:
    try:
        await bot.send_message(tg_id, text)
    except Exception:
        pass  # пользователь мог заблокировать бота


async def _show_card(cb: CallbackQuery, level: int, t) -> None:
    await _safe_edit(cb.message, ui.admin_card(t), kb.user_card_kb(level, cb.from_user.id, t))


# ---------- разделы ----------

@router.callback_query(F.data == "adm:members")
async def members_menu(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    if await _need_staff(cb) is None:
        return
    await _safe_edit(cb.message, ui.members_menu_text(), kb.members_menu_kb())
    await cb.answer()


@router.callback_query(F.data == "adm:roles")
async def roles_menu(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    if await _need_staff(cb) is None:
        return
    await _safe_edit(cb.message, ui.roles_menu_text(), kb.roles_menu_kb())
    await cb.answer()


@router.callback_query(F.data == "adm:noop")
async def noop(cb: CallbackQuery):
    await cb.answer()


# ---------- поиск ----------

@router.callback_query(F.data.startswith("adm:find:"))
async def find_start(cb: CallbackQuery, state: FSMContext):
    if await _need_staff(cb) is None:
        return
    mode = cb.data.split(":")[2]
    if mode not in ("find", "role"):
        return await cb.answer()
    await state.set_state(Find.query)
    await state.update_data(mode=mode)
    back = "adm:roles" if mode == "role" else "adm:members"
    await _safe_edit(cb.message, ui.find_prompt(), kb.cancel_kb(back))
    await cb.answer()


@router.message(Find.query, F.text)
async def find_run(message: Message, state: FSMContext):
    if await db.get_level(message.from_user.id) < 2:
        return
    mode = (await state.get_data()).get("mode", "find")
    q = message.text.strip()
    users = await db.search_users(q)
    back = "adm:roles" if mode == "role" else "adm:members"
    if not users:
        return await message.answer(ui.not_found_text(q), reply_markup=kb.cancel_kb(back))
    await state.clear()
    await message.answer(ui.results_text(q, len(users)), reply_markup=kb.results_kb(users, mode))


# ---------- списки ----------

@router.callback_query(F.data.startswith("adm:list:"))
async def show_list(cb: CallbackQuery):
    if await _need_staff(cb) is None:
        return
    _, _, kind, page = cb.data.split(":")
    if kind not in db.LIST_KINDS:
        return await cb.answer()
    page = max(0, int(page))
    rows, total = await db.list_users(kind, page * PAGE, PAGE)
    pages = max(1, -(-total // PAGE))
    if page >= pages:
        page = pages - 1
        rows, total = await db.list_users(kind, page * PAGE, PAGE)
    await _safe_edit(cb.message, ui.list_text(kind, page, pages, total), kb.list_kb(rows, kind, page, pages))
    await cb.answer()


# ---------- карточка участника ----------

@router.callback_query(F.data.startswith("adm:u:"))
async def open_card(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    level = await _need_staff(cb)
    if level is None:
        return
    t = await _target(cb, int(cb.data.split(":")[2]))
    if not t:
        return
    await _show_card(cb, level, t)
    await cb.answer()


@router.callback_query(F.data.startswith("adm:ask:"))
async def ask_confirm(cb: CallbackQuery):
    level = await _need_staff(cb)
    if level is None:
        return
    _, _, action, tid = cb.data.split(":")
    if action not in ui.ACTION_VERBS:
        return await cb.answer()
    t = await _target(cb, int(tid))
    if not t:
        return
    if not _can_act(level, cb.from_user.id, t):
        return await cb.answer("Недостаточно прав.", show_alert=True)
    await _safe_edit(cb.message, ui.confirm_text(action, t), kb.confirm_kb(action, t["tg_id"]))
    await cb.answer()


@router.callback_query(F.data.startswith("adm:do:"))
async def do_action(cb: CallbackQuery, bot: Bot):
    level = await _need_staff(cb)
    if level is None:
        return
    _, _, action, tid = cb.data.split(":")
    if action not in db.ACTIONS_SQL:
        return await cb.answer()
    t = await _target(cb, int(tid))
    if not t:
        return
    if not _can_act(level, cb.from_user.id, t):
        return await cb.answer("Недостаточно прав.", show_alert=True)
    if action == "unblack" and level < 3:
        return await cb.answer("Убрать из ЧС может Заместитель и выше.", show_alert=True)

    await db.apply_action(t["tg_id"], action)
    await db.log_action(cb.from_user.id, action, t["tg_id"])
    if action == "warn" and await db.maybe_autoban(t["tg_id"]):
        await db.log_action(cb.from_user.id, "ban", t["tg_id"], "автобан: 3 варна")
        action = "ban"
    t = await db.get_user(t["tg_id"])
    await _notify(bot, t["tg_id"], ui.target_notice(action, t))
    await _show_card(cb, level, t)
    await cb.answer(ui.ACTION_DONE[action])


# ---------- изменение данных ----------

@router.callback_query(F.data.startswith("adm:edit:"))
async def edit_menu(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    level = await _need_staff(cb)
    if level is None:
        return
    t = await _target(cb, int(cb.data.split(":")[2]))
    if not t:
        return
    if not _can_act(level, cb.from_user.id, t):
        return await cb.answer("Недостаточно прав.", show_alert=True)
    await _safe_edit(cb.message, ui.edit_menu_text(t), kb.edit_kb(t["tg_id"]))
    await cb.answer()


@router.callback_query(F.data.startswith("adm:ef:"))
async def edit_field_start(cb: CallbackQuery, state: FSMContext):
    level = await _need_staff(cb)
    if level is None:
        return
    _, _, field, tid = cb.data.split(":")
    if field not in db.EDITABLE_FIELDS:
        return await cb.answer()
    t = await _target(cb, int(tid))
    if not t:
        return
    if not _can_act(level, cb.from_user.id, t):
        return await cb.answer("Недостаточно прав.", show_alert=True)
    await state.set_state(EditField.value)
    await state.update_data(field=field, tid=t["tg_id"])
    await cb.message.answer(ui.edit_prompt(field))
    await cb.answer()


def _parse(field: str, text: str):
    t = text.strip()
    if not t:
        return None
    if field == "name":
        return t[:64]
    if field == "nick":
        return t[:32]
    try:
        n = int(t)
    except ValueError:
        return None
    if field == "age":
        return n if 5 <= n <= 99 else None
    if field == "hours":
        return n if 0 <= n <= 100000 else None
    if field == "reputation":
        return n if -9999 <= n <= 9999 else None
    return None


@router.message(EditField.value, F.text)
async def edit_field_save(message: Message, state: FSMContext):
    level = await db.get_level(message.from_user.id)
    data = await state.get_data()
    field, tid = data["field"], data["tid"]
    t = await db.get_user(tid)
    if not _can_act(level, message.from_user.id, t):
        await state.clear()
        return await message.answer("Недостаточно прав.")

    value = _parse(field, message.text)
    if value is None:
        return await message.answer("⚠️ Неверное значение. Попробуй ещё раз или нажми /start для отмены.")

    await db.update_field(tid, field, value)
    await db.log_action(message.from_user.id, "edit", tid, f"{field}={value}")
    if field == "hours":
        await db.mark_hours_verified(tid)  # админ сам выставил часы — считаются проверенными
    await state.clear()
    t = await db.get_user(tid)
    await message.answer("✅ Данные обновлены!\n\n" + ui.admin_card(t),
                         reply_markup=kb.user_card_kb(level, message.from_user.id, t))


# ---------- роли ----------

@router.callback_query(F.data.startswith("adm:role:"))
async def role_pick(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    level = await _need_staff(cb)
    if level is None:
        return
    t = await _target(cb, int(cb.data.split(":")[2]))
    if not t:
        return
    if t["status"] != "accepted":
        return await cb.answer("Роль можно выдать только принятому участнику.", show_alert=True)
    if not _can_act(level, cb.from_user.id, t):
        return await cb.answer("Недостаточно прав.", show_alert=True)
    await _safe_edit(cb.message, ui.role_pick_text(t), kb.role_pick_kb(level, t))
    await cb.answer()


@router.callback_query(F.data.startswith("adm:setrole:"))
async def set_role(cb: CallbackQuery, bot: Bot):
    level = await _need_staff(cb)
    if level is None:
        return
    _, _, role, tid = cb.data.split(":")
    if role not in roles.ROLES or role == "owner":
        return await cb.answer()
    t = await _target(cb, int(tid))
    if not t:
        return
    if t["status"] != "accepted" or not _can_act(level, cb.from_user.id, t):
        return await cb.answer("Недостаточно прав.", show_alert=True)
    if roles.level(role) >= level:
        return await cb.answer("Нельзя выдать роль не ниже своей.", show_alert=True)
    if t["role"] == role:
        return await cb.answer()

    await db.set_role(t["tg_id"], role)
    await db.log_action(cb.from_user.id, "role_take" if role == "member" else "role_give", t["tg_id"], role)
    t = await db.get_user(t["tg_id"])
    await _notify(bot, t["tg_id"], ui.role_notice(role))
    await _safe_edit(cb.message, ui.role_pick_text(t), kb.role_pick_kb(level, t))
    await cb.answer("Роль обновлена")


# ---------- часы: отметка «проверено админом» ----------

@router.callback_query(F.data.startswith("adm:hv:"))
async def verify_hours(cb: CallbackQuery):
    level = await _need_staff(cb)
    if level is None:
        return
    t = await _target(cb, int(cb.data.split(":")[2]))
    if not t:
        return
    if not _can_act(level, cb.from_user.id, t):
        return await cb.answer("Недостаточно прав.", show_alert=True)
    await db.mark_hours_verified(t["tg_id"])
    await db.log_action(cb.from_user.id, "hours_verify", t["tg_id"])
    t = await db.get_user(t["tg_id"])
    await _show_card(cb, level, t)
    await cb.answer("✔️ Часы отмечены как проверенные")
