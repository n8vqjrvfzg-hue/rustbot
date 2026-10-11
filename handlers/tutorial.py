"""Обучение новичков: после одобрения анкеты участник проходит шаги и проверку знаний."""
from aiogram import F, Router
from aiogram.types import CallbackQuery

import ui
from database import db
from keyboards.extras import rules_ok_kb, tut_quiz_kb, tut_step_kb
from utils import safe_edit

router = Router()


async def _onboarding_user(cb: CallbackQuery):
    user = await db.get_user(cb.from_user.id)
    if not user or user["status"] != "onboarding":
        if user and user["status"] == "accepted":
            await cb.answer("Обучение уже пройдено ✅")
        elif user and user["status"] == "rules":
            await cb.answer("Обучение пройдено ✅ Осталось прочитать правила: нажми /start.", show_alert=True)
        else:
            await cb.answer("Обучение доступно после одобрения анкеты.", show_alert=True)
        return None
    return user


@router.callback_query(F.data.startswith("tut:"))
async def tutorial_step(cb: CallbackQuery):
    if not await _onboarding_user(cb):
        return
    step = int(cb.data.split(":")[1])
    if not 0 <= step < len(ui.TUTORIAL_STEPS):
        return await cb.answer()
    await safe_edit(cb.message, ui.tutorial_step(step), tut_step_kb(step, len(ui.TUTORIAL_STEPS)))
    await cb.answer()


@router.callback_query(F.data.startswith("tutq:"))
async def tutorial_question(cb: CallbackQuery):
    if not await _onboarding_user(cb):
        return
    q = int(cb.data.split(":")[1])
    if not 0 <= q < len(ui.TUTORIAL_QUIZ):
        return await cb.answer()
    await safe_edit(cb.message, ui.tutorial_question(q), tut_quiz_kb(q, ui.TUTORIAL_QUIZ[q]["options"]))
    await cb.answer()


@router.callback_query(F.data.startswith("tuta:"))
async def tutorial_answer(cb: CallbackQuery):
    user = await _onboarding_user(cb)
    if not user:
        return
    _, q, opt = cb.data.split(":")
    q, opt = int(q), int(opt)
    if not 0 <= q < len(ui.TUTORIAL_QUIZ):
        return await cb.answer()
    item = ui.TUTORIAL_QUIZ[q]
    if opt != item["correct"]:
        return await cb.answer(f"Не совсем. {item['hint']}", show_alert=True)

    if q + 1 < len(ui.TUTORIAL_QUIZ):
        await safe_edit(cb.message, ui.tutorial_question(q + 1),
                        tut_quiz_kb(q + 1, ui.TUTORIAL_QUIZ[q + 1]["options"]))
        return await cb.answer("✅ Верно!")

    # последний шаг перед полным доступом: правила сообщества
    await db.set_user_status(user["tg_id"], "rules")
    await safe_edit(cb.message, ui.rules_screen(await db.get_rules_custom(), first_time=True), rules_ok_kb())
    await cb.answer("🎓 Обучение пройдено!")
