from aiogram.types import InlineKeyboardButton as Btn, InlineKeyboardMarkup as Kb

import roles
from ui import ROLE_ICONS

ASSIGNABLE = ("moderator", "admin", "deputy", "chief_admin")


def user_label(u) -> str:
    base = u["nick"] or u["name"] or str(u["tg_id"])
    label = f"{ROLE_ICONS.get(u['role'], '🎮')} {base}"
    if u["username"]:
        label += f" · @{u['username']}"
    return label[:60]


def admin_menu(level: int, maintenance: bool) -> Kb:
    rows = []
    if level >= 2:
        rows += [
            [Btn(text="👥 Управление участниками", callback_data="adm:members")],
            [Btn(text="🎭 Управление ролями", callback_data="adm:roles")],
            [Btn(text="📅 Управление ивентами", callback_data="adm:events")],
        ]
    # голосования доступны с роли модератора
    rows.append([Btn(text="🗳 Управление голосованиями", callback_data="adm:polls")])
    if level >= 2:
        rows.append([Btn(text="🚨 Экстренный сбор", callback_data="adm:em")])
        rows.append([Btn(text="📚 Факты о Rust", callback_data="adm:facts")])
    if level >= 3:
        rows.append([Btn(text="📈 Статистика админов", callback_data="adm:stats")])
        state = "ВКЛ 🔴" if maintenance else "ВЫКЛ 🟢"
        rows.append([Btn(text=f"🛠 Тех. работы: {state}", callback_data="adm:maint")])
        rows.append([Btn(text="⚙️ Настройки", callback_data="adm:settings")])
    rows.append([Btn(text="⬅️ Назад", callback_data="menu")])
    return Kb(inline_keyboard=rows)


def members_menu_kb() -> Kb:
    return Kb(inline_keyboard=[
        [Btn(text="🔍 Найти участника", callback_data="adm:find:find")],
        [Btn(text="📋 Список участников", callback_data="adm:list:all:0")],
        [
            Btn(text="🚫 Забаненные", callback_data="adm:list:banned:0"),
            Btn(text="⛔ Чёрный список", callback_data="adm:list:black:0"),
        ],
        [Btn(text="⬅️ Назад", callback_data="admin")],
    ])


def roles_menu_kb() -> Kb:
    return Kb(inline_keyboard=[
        [Btn(text="🔍 Найти участника", callback_data="adm:find:role")],
        [Btn(text="🛡 Список администрации", callback_data="adm:list:staff:0")],
        [Btn(text="⬅️ Назад", callback_data="admin")],
    ])


def cancel_kb(target: str) -> Kb:
    return Kb(inline_keyboard=[[Btn(text="❌ Отмена", callback_data=target)]])


def results_kb(users, mode: str) -> Kb:
    prefix = "adm:role:" if mode == "role" else "adm:u:"
    back = "adm:roles" if mode == "role" else "adm:members"
    rows = [[Btn(text=user_label(u), callback_data=f"{prefix}{u['tg_id']}")] for u in users]
    rows.append([
        Btn(text="🔍 Новый поиск", callback_data=f"adm:find:{mode}"),
        Btn(text="⬅️ Назад", callback_data=back),
    ])
    return Kb(inline_keyboard=rows)


def list_kb(users, kind: str, page: int, pages: int) -> Kb:
    prefix = "adm:role:" if kind == "staff" else "adm:u:"
    rows = [[Btn(text=user_label(u), callback_data=f"{prefix}{u['tg_id']}")] for u in users]
    if pages > 1:
        nav = []
        if page > 0:
            nav.append(Btn(text="⬅️", callback_data=f"adm:list:{kind}:{page - 1}"))
        nav.append(Btn(text=f"{page + 1}/{pages}", callback_data="adm:noop"))
        if page < pages - 1:
            nav.append(Btn(text="➡️", callback_data=f"adm:list:{kind}:{page + 1}"))
        rows.append(nav)
    rows.append([Btn(text="⬅️ Назад", callback_data="adm:roles" if kind == "staff" else "adm:members")])
    return Kb(inline_keyboard=rows)


def user_card_kb(viewer_level: int, viewer_id: int, t) -> Kb:
    rows = []
    tid = t["tg_id"]
    can = viewer_id != tid and viewer_level >= 2 and viewer_level > roles.level(t["role"])
    if can:
        rows.append([
            Btn(text="⚠️ Варн", callback_data=f"adm:do:warn:{tid}"),
            Btn(text="➖ Снять варн", callback_data=f"adm:do:unwarn:{tid}"),
        ])
        st = t["status"]
        if st == "banned":
            rows.append([Btn(text="✅ Разбанить", callback_data=f"adm:do:unban:{tid}")])
        elif st == "blacklisted":
            if viewer_level >= 3:
                rows.append([Btn(text="♻️ Убрать из ЧС", callback_data=f"adm:do:unblack:{tid}")])
        else:
            rows.append([
                Btn(text="🚫 Бан", callback_data=f"adm:ask:ban:{tid}"),
                Btn(text="👢 Кик из бота", callback_data=f"adm:ask:kick:{tid}"),
            ])
            rows.append([Btn(text="⛔ В чёрный список", callback_data=f"adm:ask:black:{tid}")])
        rows.append([Btn(text="✏️ Изменить данные", callback_data=f"adm:edit:{tid}")])
        if t["hours_source"] == "manual":
            rows.append([Btn(text="✔️ Часы проверены", callback_data=f"adm:hv:{tid}")])
        if st == "accepted":
            rows.append([Btn(text="🎭 Роль", callback_data=f"adm:role:{tid}")])
    rows.append([Btn(text="⬅️ К списку", callback_data="adm:members")])
    return Kb(inline_keyboard=rows)


def confirm_kb(action: str, tid: int) -> Kb:
    return Kb(inline_keyboard=[[
        Btn(text="✅ Да, подтвердить", callback_data=f"adm:do:{action}:{tid}"),
        Btn(text="❌ Отмена", callback_data=f"adm:u:{tid}"),
    ]])


def edit_kb(tid: int) -> Kb:
    return Kb(inline_keyboard=[
        [
            Btn(text="🏷 Имя", callback_data=f"adm:ef:name:{tid}"),
            Btn(text="🎮 Ник", callback_data=f"adm:ef:nick:{tid}"),
        ],
        [
            Btn(text="🎂 Возраст", callback_data=f"adm:ef:age:{tid}"),
            Btn(text="⏱ Часы", callback_data=f"adm:ef:hours:{tid}"),
        ],
        [Btn(text="⭐ Репутация", callback_data=f"adm:ef:reputation:{tid}")],
        [Btn(text="⬅️ Назад", callback_data=f"adm:u:{tid}")],
    ])


def role_pick_kb(viewer_level: int, t) -> Kb:
    tid = t["tg_id"]
    rows = []
    for role in ASSIGNABLE:
        if roles.level(role) < viewer_level and role != t["role"]:
            rows.append([Btn(
                text=f"{ROLE_ICONS[role]} {roles.title(role)}",
                callback_data=f"adm:setrole:{role}:{tid}",
            )])
    if t["role"] != "member":
        rows.append([Btn(text="➖ Снять роль", callback_data=f"adm:setrole:member:{tid}")])
    rows.append([Btn(text="⬅️ Назад", callback_data=f"adm:u:{tid}")])
    return Kb(inline_keyboard=rows)
