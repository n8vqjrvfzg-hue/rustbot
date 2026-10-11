"""Привязка Steam: часы в Rust, инвентарь (скины) и DLC."""
import logging
import re

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

import config
import steam
import timeutil
import ui
from database import db
from handlers.common import get_member
from keyboards import extras as kb
from utils import safe_edit

router = Router()
log = logging.getLogger(__name__)
COOLDOWN_MIN = 10


class SteamLink(StatesGroup):
    query = State()
    verify = State()


class ManualHours(StatesGroup):
    value = State()


async def _dlc_counts(uid: int) -> tuple:
    return len(await db.user_dlc_ids(uid)), len(await db.get_dlc_list())


async def _menu(uid: int):
    u = await db.get_user(uid)
    return ui.steam_menu_text(u, await _dlc_counts(uid)), kb.steam_kb(bool(u["steam_id"]))


def _error_text(e: steam.SteamError) -> str:
    return {
        "private": "Инвентарь закрыт. Открой его: Steam → Настройки приватности → «Инвентарь» → Публичный.",
        "rate": "Steam временно ограничил запросы. Попробуй через минуту.",
    }.get(str(e), "Steam сейчас не отвечает. Попробуй позже.")


@router.callback_query(F.data == "steam")
async def steam_menu(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    me = await get_member(cb)
    if not me:
        return
    text, markup = await _menu(me["tg_id"])
    await safe_edit(cb.message, text, markup)
    await cb.answer()


# ---------- привязка ----------

@router.callback_query(F.data == "steam:link")
async def link_start(cb: CallbackQuery, state: FSMContext):
    me = await get_member(cb)
    if not me:
        return
    if not config.STEAM_API_KEY:
        return await cb.answer("Привязка Steam пока не настроена администрацией.", show_alert=True)
    if me["steam_id"]:
        return await cb.answer("Steam уже привязан.", show_alert=True)
    await state.set_state(SteamLink.query)
    await safe_edit(cb.message, ui.steam_link_prompt(), kb.steam_cancel_kb())
    await cb.answer()


@router.message(SteamLink.query, F.text)
async def link_query(message: Message, state: FSMContext):
    me = await db.get_user(message.from_user.id)
    if not me or me["status"] != "accepted":
        return await state.clear()
    parsed = steam.parse_steam_input(message.text)
    if not parsed:
        return await message.answer("⚠️ Не понял. Пришли ссылку на профиль Steam, SteamID64 или короткое имя.")

    wait = await message.answer("🔎 Ищу аккаунт…")
    try:
        sid = parsed[1] if parsed[0] == "id" else await steam.resolve_vanity(parsed[1])
        player = await steam.get_player(sid) if sid else None
    except steam.SteamError as e:
        log.warning("Steam: %s", e)
        return await wait.edit_text(f"⚠️ {_error_text(e)}", reply_markup=kb.steam_cancel_kb())
    if not player:
        return await wait.edit_text("⚠️ Аккаунт не найден. Проверь ссылку.", reply_markup=kb.steam_cancel_kb())
    if await db.steam_id_taken(player["steamid"], me["tg_id"]):
        return await wait.edit_text(
            "⚠️ Этот Steam-аккаунт уже привязан к другому участнику. Если это твой — напиши админам.",
            reply_markup=kb.steam_cancel_kb(),
        )

    code = steam.make_code()
    await state.update_data(steam_id=player["steamid"], code=code)
    await state.set_state(SteamLink.verify)
    await wait.edit_text(ui.steam_verify_prompt(code, player.get("personaname", "")), reply_markup=kb.steam_verify_kb())


@router.callback_query(SteamLink.verify, F.data == "steam:check")
async def link_check(cb: CallbackQuery, state: FSMContext, bot: Bot):
    me = await get_member(cb)
    if not me:
        return
    data = await state.get_data()
    sid, code = data["steam_id"], data["code"]
    try:
        player = await steam.get_player(sid)
    except steam.SteamError as e:
        return await cb.answer(_error_text(e), show_alert=True)
    name = (player or {}).get("personaname", "")
    if code.lower() not in name.lower():
        return await cb.answer(
            "Код пока не виден в нике Steam. Подожди полминуты после сохранения и нажми снова.", show_alert=True
        )
    if await db.steam_id_taken(sid, me["tg_id"]):
        await state.clear()
        return await cb.answer("Этот аккаунт уже привязан к другому участнику.", show_alert=True)

    try:
        hours = await steam.get_rust_hours(sid)
    except steam.SteamError as e:
        return await cb.answer(_error_text(e), show_alert=True)

    clean = re.sub(re.escape(code), "", name, flags=re.I).strip(" -|") or name
    old_hours, old_source = me["hours"], me["hours_source"]
    await db.set_steam_link(me["tg_id"], sid, clean, hours)
    await state.clear()

    # указал вручную заметно больше, чем есть в Steam — сообщаем админам
    if hours is not None and old_source == "manual" and old_hours and old_hours > hours * 1.2 + 5:
        try:
            fresh = await db.get_user(me["tg_id"])
            await bot.send_message(
                config.ADMIN_GROUP_ID,
                ui.hours_mismatch_report(fresh, old_hours, hours),
                message_thread_id=config.COMPLAINTS_TOPIC_ID,
            )
        except Exception as e:
            log.warning("Не удалось отправить отчёт о расхождении часов: %s", e)

    await safe_edit(cb.message, ui.steam_linked_text(hours), kb.steam_after_link_kb())
    await cb.answer("✅ Steam привязан")


# ---------- обновление и отвязка ----------

@router.callback_query(F.data == "steam:sync")
async def sync_now(cb: CallbackQuery):
    me = await get_member(cb)
    if not me:
        return
    if not me["steam_id"]:
        return await cb.answer("Steam не привязан.", show_alert=True)
    if me["steam_synced_at"] and me["steam_synced_at"] > timeutil.in_minutes(-COOLDOWN_MIN):
        return await cb.answer(f"Обновлять можно раз в {COOLDOWN_MIN} минут.", show_alert=True)
    try:
        hours = await steam.get_rust_hours(me["steam_id"])
    except steam.SteamError as e:
        return await cb.answer(_error_text(e), show_alert=True)
    if hours is None:
        await db.touch_steam_sync(me["tg_id"])
        text, markup = await _menu(me["tg_id"])
        await safe_edit(cb.message, text, markup)
        return await cb.answer("Steam не отдаёт часы — открой «Данные об играх».", show_alert=True)
    await db.update_steam_hours(me["tg_id"], hours)
    text, markup = await _menu(me["tg_id"])
    await safe_edit(cb.message, text, markup)
    await cb.answer("✅ Часы обновлены")


@router.callback_query(F.data == "steam:unlink")
async def unlink(cb: CallbackQuery):
    me = await get_member(cb)
    if not me:
        return
    await db.unlink_steam(me["tg_id"])
    text, markup = await _menu(me["tg_id"])
    await safe_edit(cb.message, text, markup)
    await cb.answer("Steam отвязан. Часы теперь помечены как непроверенные.", show_alert=True)


# ---------- ручной ввод часов ----------

@router.callback_query(F.data == "steam:manual")
async def manual_start(cb: CallbackQuery, state: FSMContext):
    me = await get_member(cb)
    if not me:
        return
    if me["steam_id"]:
        return await cb.answer("Часы берутся из Steam автоматически.", show_alert=True)
    await state.set_state(ManualHours.value)
    await safe_edit(cb.message, ui.manual_hours_prompt(), kb.steam_cancel_kb())
    await cb.answer()


@router.message(ManualHours.value, F.text)
async def manual_save(message: Message, state: FSMContext):
    me = await db.get_user(message.from_user.id)
    if not me or me["status"] != "accepted":
        return await state.clear()
    raw = message.text.strip()
    if not raw.isdigit() or int(raw) > 100000:
        return await message.answer("⚠️ Отправь количество часов числом, например <b>500</b>.")
    await db.set_manual_hours(me["tg_id"], int(raw))
    await state.clear()
    text, markup = await _menu(me["tg_id"])
    await message.answer("✅ Часы сохранены (не проверено).\n\n" + text, reply_markup=markup)


# ---------- инвентарь (скины) ----------

@router.callback_query(F.data == "steam:inv")
async def inventory(cb: CallbackQuery):
    me = await get_member(cb)
    if not me:
        return
    if not me["steam_id"]:
        return await cb.answer("Сначала привяжи Steam.", show_alert=True)
    if me["inv_updated"] and me["inv_updated"] > timeutil.in_minutes(-COOLDOWN_MIN):
        res = {"total": me["inv_items"], "unique": me["inv_unique"], "marketable": me["inv_marketable"]}
        await safe_edit(cb.message, ui.steam_inventory_text(res), kb.steam_kb(True))
        return await cb.answer("Недавно уже считали — показываю сохранённое.")

    await cb.answer("Считаю…")
    await safe_edit(cb.message, "⏳ Считаю инвентарь, это может занять до минуты…", None)
    try:
        res = await steam.get_inventory(me["steam_id"])
    except steam.SteamError as e:
        return await safe_edit(cb.message, f"⚠️ {_error_text(e)}", kb.steam_kb(True))
    await db.set_inventory(me["tg_id"], res["total"], res["unique"], res["marketable"])
    await safe_edit(cb.message, ui.steam_inventory_text(res), kb.steam_kb(True))


# ---------- DLC (со слов участника) ----------

async def _show_dlc(cb: CallbackQuery, uid: int) -> None:
    dlcs = await db.get_dlc_list()
    owned = await db.user_dlc_ids(uid)
    await safe_edit(cb.message, ui.steam_dlc_text(len(owned), len(dlcs)), kb.dlc_kb(dlcs, owned))


@router.callback_query(F.data == "steam:dlc")
async def dlc_menu(cb: CallbackQuery):
    me = await get_member(cb)
    if not me:
        return
    if not me["steam_id"]:
        return await cb.answer("Сначала привяжи Steam.", show_alert=True)
    if not await db.get_dlc_list():
        await cb.answer("Загружаю список DLC…")
        try:
            await db.save_dlc_list(await steam.get_dlc_list())
        except steam.SteamError:
            return await safe_edit(
                cb.message, "⚠️ Не удалось загрузить список DLC. Попробуй позже.", kb.steam_kb(True)
            )
    else:
        await cb.answer()
    await _show_dlc(cb, me["tg_id"])


@router.callback_query(F.data.startswith("dlc:"))
async def dlc_toggle(cb: CallbackQuery):
    me = await get_member(cb)
    if not me:
        return
    appid = int(cb.data.split(":")[1])
    if appid not in {d["appid"] for d in await db.get_dlc_list()}:
        return await cb.answer()
    await db.toggle_user_dlc(me["tg_id"], appid)
    await _show_dlc(cb, me["tg_id"])
    await cb.answer("Сохранено")
