"""Кнопки: игровые роли, факты, экстренный сбор, статистика, настройки."""
from aiogram.types import InlineKeyboardButton as Btn, InlineKeyboardMarkup as Kb

import roles
from keyboards.admin import user_label
from ui import TIER_LABELS


# ---------- игровые роли ----------

def grole_kb(selected: list) -> Kb:
    buttons = []
    for key, (icon, title, _) in roles.GAME_ROLES.items():
        mark = "✅ " if key in selected else ""
        buttons.append(Btn(text=f"{mark}{icon} {title}", callback_data=f"grole:{key}"))
    rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    rows.append([Btn(text="⬅️ Назад", callback_data="profile")])
    return Kb(inline_keyboard=rows)


# ---------- факты ----------

def facts_kb(tier: str, cur: int) -> Kb:
    switch = [
        Btn(text=("• " if key == tier else "") + icon, callback_data=f"facts:t:{key}")
        for key, (icon, _) in TIER_LABELS.items()
    ]
    return Kb(inline_keyboard=[
        [Btn(text="🎲 Ещё факт", callback_data=f"facts:n:{tier}:{cur}")],
        switch,
        [Btn(text="⬅️ Назад", callback_data="menu")],
    ])


# ---------- экстренный сбор ----------

def em_cancel_kb() -> Kb:
    return Kb(inline_keyboard=[[Btn(text="❌ Отмена", callback_data="admin")]])


def em_confirm_kb() -> Kb:
    return Kb(inline_keyboard=[[
        Btn(text="🚨 Разослать всем", callback_data="adm:em:pub"),
        Btn(text="❌ Отмена", callback_data="admin"),
    ]])


def em_ack_kb(eid: int) -> Kb:
    return Kb(inline_keyboard=[[Btn(text="✅ Иду!", callback_data=f"em:ack:{eid}")]])


def em_acked_kb() -> Kb:
    return Kb(inline_keyboard=[[Btn(text="✅ Ты отметился", callback_data="em:noop")]])


def em_card_kb(eid: int) -> Kb:
    return Kb(inline_keyboard=[
        [Btn(text="🔄 Обновить", callback_data=f"adm:em:view:{eid}")],
        [Btn(text="⬅️ В админ-меню", callback_data="admin")],
    ])


# ---------- статистика ----------

PERIODS = {0: "Всё время", 30: "30 дней", 7: "7 дней"}


def stats_kb(rows, days: int) -> Kb:
    period_row = [
        Btn(text=("• " if d == days else "") + label, callback_data=f"adm:stp:{d}")
        for d, label in PERIODS.items()
    ]
    kb_rows = [period_row]
    for u, total, _ in rows:
        kb_rows.append([Btn(text=f"{user_label(u)} · {total}", callback_data=f"adm:stu:{u['tg_id']}:{days}")])
    kb_rows.append([Btn(text="⬅️ Назад", callback_data="admin")])
    return Kb(inline_keyboard=kb_rows)


def stats_detail_kb(days: int) -> Kb:
    return Kb(inline_keyboard=[[Btn(text="⬅️ К списку", callback_data=f"adm:stp:{days}")]])


# ---------- настройки ----------

def settings_kb(v: dict) -> Kb:
    def on(x: str) -> str:
        return "🟢 ВКЛ" if x == "1" else "🔴 ВЫКЛ"

    return Kb(inline_keyboard=[
        [Btn(text=f"📝 Приём анкет: {on(v['apps_open'])}", callback_data="adm:set:apps_open")],
        [Btn(text=f"⚠️ Автобан (3 варна): {on(v['autoban'])}", callback_data="adm:set:autoban")],
        [Btn(text=f"⭐ Оценок в сутки: {v['rep_per_day']}", callback_data="adm:set:rep_per_day")],
        [Btn(text="📜 Правила сообщества", callback_data="adm:rules")],
        [Btn(text="⬅️ Назад", callback_data="admin")],
    ])


# ---------- правила ----------

def rules_ok_kb() -> Kb:
    return Kb(inline_keyboard=[[Btn(text="✅ Прочитал(а) и согласен(на)", callback_data="rules:ok")]])


def rules_view_kb() -> Kb:
    return Kb(inline_keyboard=[[Btn(text="⬅️ Назад", callback_data="menu")]])


def rules_admin_kb() -> Kb:
    return Kb(inline_keyboard=[
        [Btn(text="✏️ Изменить текст", callback_data="adm:rules:edit")],
        [Btn(text="⬅️ К настройкам", callback_data="adm:settings")],
    ])


def rules_cancel_kb() -> Kb:
    return Kb(inline_keyboard=[[Btn(text="❌ Отмена", callback_data="adm:rules")]])


# ---------- прайм-тайм ----------

PRIME_PRESETS = {
    "morning": "06:00–12:00",
    "day": "12:00–18:00",
    "evening": "18:00–00:00",
    "night": "00:00–06:00",
    "flex": "Гибкий график",
}
PRIME_LABELS = {
    "morning": "🌅 Утро 06–12",
    "day": "☀️ День 12–18",
    "evening": "🌆 Вечер 18–00",
    "night": "🌙 Ночь 00–06",
    "flex": "🔄 Гибкий график",
}


def prime_kb(prefix: str) -> Kb:
    buttons = [Btn(text=PRIME_LABELS[k], callback_data=f"{prefix}:{k}") for k in PRIME_PRESETS]
    rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    return Kb(inline_keyboard=rows)


# ---------- Steam ----------

def steam_kb(linked: bool) -> Kb:
    if linked:
        return Kb(inline_keyboard=[
            [Btn(text="🔄 Обновить часы", callback_data="steam:sync")],
            [
                Btn(text="🎒 Инвентарь", callback_data="steam:inv"),
                Btn(text="🎁 DLC", callback_data="steam:dlc"),
            ],
            [Btn(text="❌ Отвязать Steam", callback_data="steam:unlink")],
            [Btn(text="⬅️ Назад", callback_data="profile")],
        ])
    return Kb(inline_keyboard=[
        [Btn(text="🔗 Привязать Steam", callback_data="steam:link")],
        [Btn(text="✏️ Указать часы вручную", callback_data="steam:manual")],
        [Btn(text="⬅️ Назад", callback_data="profile")],
    ])


def steam_after_link_kb() -> Kb:
    return Kb(inline_keyboard=[
        [Btn(text="🎒 Посчитать инвентарь", callback_data="steam:inv")],
        [Btn(text="🎁 Отметить DLC", callback_data="steam:dlc")],
        [Btn(text="⬅️ К Steam", callback_data="steam")],
    ])


def steam_verify_kb() -> Kb:
    return Kb(inline_keyboard=[
        [Btn(text="✅ Проверить", callback_data="steam:check")],
        [Btn(text="❌ Отмена", callback_data="steam")],
    ])


def steam_cancel_kb() -> Kb:
    return Kb(inline_keyboard=[[Btn(text="❌ Отмена", callback_data="steam")]])


def dlc_kb(dlcs, owned: set) -> Kb:
    rows = [
        [Btn(text=f"{'✅' if d['appid'] in owned else '⬜️'} {d['name'][:40]}", callback_data=f"dlc:{d['appid']}")]
        for d in dlcs
    ]
    rows.append([Btn(text="⬅️ К Steam", callback_data="steam")])
    return Kb(inline_keyboard=rows)


# ---------- обучение ----------

def tut_start_kb() -> Kb:
    return Kb(inline_keyboard=[[Btn(text="📚 Начать обучение", callback_data="tut:0")]])


def tut_step_kb(step: int, total: int) -> Kb:
    nav = []
    if step > 0:
        nav.append(Btn(text="⬅️ Назад", callback_data=f"tut:{step - 1}"))
    if step < total - 1:
        nav.append(Btn(text="➡️ Далее", callback_data=f"tut:{step + 1}"))
        return Kb(inline_keyboard=[nav])
    return Kb(inline_keyboard=[nav, [Btn(text="🧠 Пройти проверку знаний", callback_data="tutq:0")]])


def tut_quiz_kb(q: int, options) -> Kb:
    return Kb(inline_keyboard=[
        [Btn(text=opt, callback_data=f"tuta:{q}:{i}")] for i, opt in enumerate(options)
    ])


# ---------- админ: факты ----------

def facts_admin_kb() -> Kb:
    return Kb(inline_keyboard=[
        [Btn(text="➕ Добавить факт", callback_data="adm:fn")],
        [Btn(text="📋 Добавленные факты", callback_data="adm:fl")],
        [Btn(text="⬅️ Назад", callback_data="admin")],
    ])


def fact_tier_kb() -> Kb:
    rows = [[Btn(text=f"{icon} {label}", callback_data=f"adm:fn:{key}")] for key, (icon, label) in TIER_LABELS.items()]
    rows.append([Btn(text="❌ Отмена", callback_data="adm:facts")])
    return Kb(inline_keyboard=rows)


def fact_cancel_kb() -> Kb:
    return Kb(inline_keyboard=[[Btn(text="❌ Отмена", callback_data="adm:facts")]])


def fact_list_kb(rows) -> Kb:
    items = [
        [Btn(text=f"{TIER_LABELS[r['tier']][0]} #{r['id']} · {r['text'][:30]}", callback_data=f"adm:fv:{r['id']}")]
        for r in rows
    ]
    items.append([Btn(text="⬅️ Назад", callback_data="adm:facts")])
    return Kb(inline_keyboard=items)


def fact_view_kb(fid: int) -> Kb:
    return Kb(inline_keyboard=[
        [Btn(text="🗑 Удалить", callback_data=f"adm:fd:{fid}")],
        [Btn(text="⬅️ К списку", callback_data="adm:fl")],
    ])

def cancel_kb() -> Kb:
    """Кнопка отмены (вернуться в главное меню)."""
    return Kb(inline_keyboard=[[Btn(text="❌ Отмена", callback_data="home")]])

