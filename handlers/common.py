from aiogram.types import CallbackQuery

from database import db


async def get_member(cb: CallbackQuery):
    """Возвращает пользователя, если анкета принята и обучение пройдено. Иначе алерт и None."""
    user = await db.get_user(cb.from_user.id)
    if user and user["status"] == "onboarding":
        await cb.answer("Сначала пройди обучение: нажми /start.", show_alert=True)
        return None
    if user and user["status"] == "rules":
        await cb.answer("Сначала прочитай правила: нажми /start.", show_alert=True)
        return None
    if not user or user["status"] != "accepted":
        await cb.answer("Сначала нужно пройти анкету.", show_alert=True)
        return None
    return user


async def need_level(cb: CallbackQuery, minimum: int) -> int | None:
    """Возвращает уровень роли, если он не ниже minimum. Иначе алерт и None."""
    level = await db.get_level(cb.from_user.id)
    if level < minimum:
        await cb.answer("Нет доступа.", show_alert=True)
        return None
    return level
