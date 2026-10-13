from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

import ui
from database import db
from keyboards.admin import admin_menu
from handlers import broadcasts, user_messaging

router = Router()


async def _staff_level(cb: CallbackQuery) -> int | None:
    level = await db.get_level(cb.from_user.id)
    if level < 1:
        await cb.answer("Нет доступа.", show_alert=True)
        return None
    return level


async def _render(cb: CallbackQuery, level: int) -> None:
    user = await db.get_user(cb.from_user.id)
    maintenance = await db.get_setting("maintenance") == "1"
    await cb.message.edit_text(
        ui.admin_text(user, maintenance),
        reply_markup=admin_menu(level, maintenance),
    )


@router.callback_query(F.data == "admin")
async def open_admin(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    level = await _staff_level(cb)
    if level is None:
        return
    await _render(cb, level)
    await cb.answer()


@router.callback_query(F.data == "adm:soon")
async def soon(cb: CallbackQuery):
    if await _staff_level(cb) is None:
        return
    await cb.answer("Этот раздел появится на следующем этапе.", show_alert=True)


@router.callback_query(F.data == "adm:maint")
async def toggle_maintenance(cb: CallbackQuery):
    level = await _staff_level(cb)
    if level is None:
        return
    if level < 3:
        return await cb.answer("Доступно с роли Заместитель.", show_alert=True)
    new = "0" if await db.get_setting("maintenance") == "1" else "1"
    await db.set_setting("maintenance", new)
    await _render(cb, level)
    await cb.answer("Режим тех. работ включён" if new == "1" else "Режим тех. работ выключен")


router.include_router(broadcasts.router)
router.include_router(user_messaging.router)
