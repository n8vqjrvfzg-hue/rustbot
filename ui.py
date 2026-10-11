"""Единое оформление всех экранов бота."""
import html
from datetime import datetime

import calendar

import roles
import timeutil

LINE = "▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬"

ROLE_ICONS = {
    "owner": "👑",
    "chief_admin": "💎",
    "deputy": "🔱",
    "admin": "🛡",
    "moderator": "⚔️",
    "member": "🎮",
}


def esc(x) -> str:
    return html.escape(str(x)) if x not in (None, "") else "—"


def header(icon: str, title: str) -> str:
    return f"✦ {icon} <b>{title}</b> ✦\n{LINE}"


def quote(*lines: str) -> str:
    return "\n".join(lines)


def role_badge(role: str | None) -> str:
    return f"{ROLE_ICONS.get(role or 'member', '🎮')} {roles.title(role)}"


def warn_icon(n: int) -> str:
    return "🟢" if n == 0 else ("🟡" if n < 3 else "🔴")


def signed(n: int) -> str:
    return f"+{n}" if n > 0 else str(n)


def progress(step: int, total: int) -> str:
    return "▰" * step + "▱" * (total - step) + f"  {step}/{total}"


def fmt_date(s: str | None) -> str:
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d").strftime("%d.%m.%Y")
    except Exception:
        return "—"


def display_name(u) -> str:
    return esc(u["name"] or u["nick"] or "друг")


# ---------- экраны ----------

def menu_text(u) -> str:
    icon, title, _, _ = rank_info(u["hours"])
    return (
        f"{header('🏠', 'ГЛАВНОЕ МЕНЮ')}\n\n"
        f"Привет, <b>{display_name(u)}</b>! 👋\n"
        f"{icon} {title}  ·  ⭐ {signed(u['reputation'])}\n\n"
        "Выбери раздел 👇"
    )


def guest_text() -> str:
    return (
        f"{header('👋', 'ДОБРО ПОЖАЛОВАТЬ')}\n\n"
        "Это закрытый бот сообщества.\n"
        "Чтобы получить доступ ко всем функциям, заполни короткую анкету — "
        "администрация рассмотрит её в ближайшее время."
    )


def pending_text() -> str:
    return (
        f"{header('⏳', 'АНКЕТА НА РАССМОТРЕНИИ')}\n\n"
        "Мы уже получили твою анкету и скоро сообщим решение."
    )


def profile_text(u, rank: int | None = None, dlc=None) -> str:
    tg = f"@{html.escape(u['username'])}" if u["username"] else "скрыт"
    age = f"{u['age']} {years(u['age'])}" if u["age"] else "возраст не указан"
    warns = u["warns"]
    rep_line = f"⭐ Рейтинг: <b>{signed(u['reputation'])}</b>" + (f"  ·  🏆 #{rank} в топе" if rank else "")
    game = [
        game_roles_line(u),
        f"⏱ Часов в Rust: <b>{esc(u['hours'])}</b>  ·  {hours_badge(u)}",
        prime_line(u),
    ]
    account = [f"📱 Telegram: {tg}"]
    if u["steam_id"]:
        account.append(f"🎮 Steam: <a href='https://steamcommunity.com/profiles/{u['steam_id']}'>{esc(u['steam_name'])}</a>")
    account += [f"📅 В боте с: <b>{fmt_date(u['created_at'])}</b>", f"🆔 <code>{u['tg_id']}</code>"]

    text = (
        f"{header('👤', 'ПРОФИЛЬ')}\n\n"
        f"🏷 <b>{esc(u['nick'])}</b>\n"
        f"<i>{esc(u['name'])} · {age}</i>\n"
        f"{role_badge(u['role'])}\n\n"
        f"{rank_block(u['hours'])}\n\n"
        + section("ИГРА", *game)
        + "\n\n"
        + section("РЕПУТАЦИЯ", rep_line, f"{warn_icon(warns)} Варны: {bar(min(warns, 3) / 3, 3)} <b>{warns}/3</b>")
        + "\n\n"
    )
    inv = inventory_lines(u, dlc)
    if inv:
        text += section("ИНВЕНТАРЬ", *inv) + "\n\n"
    return text + section("АККАУНТ", *account)


def notif_text() -> str:
    return (
        f"{header('🔔', 'УВЕДОМЛЕНИЯ')}\n\n"
        "Выбери, о чём бот может тебе писать.\n"
        "🔔 — включено, 🔕 — выключено. Нажми на пункт, чтобы переключить."
    )


def composition_text(data: dict, channel_count) -> str:
    staff = data["staff"]
    staff_total = sum(staff.values())
    staff_lines = [
        f"{ROLE_ICONS[r]} {roles.title(r)} — <b>{staff[r]}</b>"
        for r in ("owner", "chief_admin", "deputy", "admin", "moderator")
        if staff.get(r)
    ] or ["—"]
    return (
        f"{header('📊', 'СОСТАВ')}\n\n"
        + section(
            "СООБЩЕСТВО",
            f"📣 Участников в канале: <b>{channel_count}</b>",
            f"🎮 Участников в боте: <b>{data['members']}</b>",
        )
        + "\n\n"
        + section(f"АДМИНИСТРАЦИЯ · {staff_total}", *staff_lines)
        + "\n\n"
        + section(
            "АНКЕТЫ",
            f"✅ Принято: <b>{data['apps_accepted']}</b>",
            f"⏳ На рассмотрении: <b>{data['apps_pending']}</b>",
        )
    )


def admin_text(u, maintenance: bool) -> str:
    state = "🔴 включены" if maintenance else "🟢 выключены"
    return (
        f"{header('🛠', 'АДМИН-МЕНЮ')}\n\n"
        + quote(
            f"Ваш доступ: {role_badge(u['role'])}",
            f"Тех. работы: {state}",
        )
    )


def maintenance_text() -> str:
    return (
        f"{header('🛠', 'ТЕХНИЧЕСКИЕ РАБОТЫ')}\n\n"
        "Бот временно недоступен. Загляни чуть позже — мы скоро вернёмся!"
    )


# ---------- анкета ----------

ANKETA_QUESTIONS = [
    ("🏷", "Как тебя зовут?"),
    ("🎮", "Какой у тебя игровой ник?"),
    ("🎂", "Сколько тебе лет?\n<i>Напиши числом, например 18</i>"),
    ("⏱", "Сколько часов у тебя в Rust?\n<i>Напиши числом, например 500. Позже в профиле можно привязать Steam, и часы будут подтверждаться автоматически. За указание неверных часов администрация вправе наказать по правилам.</i>"),
    ("🕒", f"В какое время ты обычно играешь (прайм-тайм)?\n<i>Время по {timeutil.TZ_LABEL}. Выбери вариант кнопкой или напиши свой, например 19:00-23:00</i>"),
    ("💬", "Расскажи о себе и откуда узнал о нас."),
]


def anketa_question(step: int) -> str:
    icon, q = ANKETA_QUESTIONS[step - 1]
    return f"{header('📝', 'АНКЕТА')}\n{progress(step, len(ANKETA_QUESTIONS))}\n\n{icon} {q}"


def anketa_sent_text() -> str:
    return (
        f"{header('✅', 'АНКЕТА ОТПРАВЛЕНА')}\n\n"
        "Администрация рассмотрит её в ближайшее время. "
        "Как только будет решение — мы напишем тебе сюда."
    )


def application_card(app_id: int, user, data: dict, about: str) -> str:
    tg = f"@{html.escape(user.username)}" if user.username else "нет"
    title = f"НОВАЯ АНКЕТА #{app_id}"
    prime = esc(data["prime"]) + (f" {timeutil.TZ_LABEL}" if data["prime"][:1].isdigit() else "")
    return (
        f"{header('📝', title)}\n\n"
        f"🏷 Имя: <b>{esc(data['name'])}</b>\n"
        f"🎮 Ник: <b>{esc(data['nick'])}</b>\n"
        f"🎂 Возраст: <b>{data['age']}</b>\n"
        f"⏱ Часов в Rust: <b>{data['hours']}</b> <i>(со слов, не проверено)</i>\n"
        f"🕒 Прайм-тайм: <b>{prime}</b>\n\n"
        f"📱 Telegram: {tg}\n"
        f"🆔 <code>{user.id}</code>\n\n"
        f"💬 <b>О себе</b>\n{esc(about)}"
    )


# ---------- игровые роли ----------


def accepted_text() -> str:
    return (
        f"{header('🎉', 'АНКЕТА ПРИНЯТА')}\n\n"
        "Добро пожаловать в сообщество! Осталось пройти короткое обучение и прочитать правила — "
        "после этого откроются все разделы бота."
    )


def rejected_text() -> str:
    return (
        f"{header('😔', 'АНКЕТА ОТКЛОНЕНА')}\n\n"
        "К сожалению, в этот раз не получилось. "
        "Ты можешь подать анкету ещё раз через /start."
    )


# ---------- управление участниками и ролями ----------

STATUS_BADGES = {
    "accepted": "✅ Активен",
    "onboarding": "📚 Проходит обучение",
    "rules": "📜 Читает правила",
    "pending": "⏳ Ждёт решения по анкете",
    "rejected": "❌ Анкета отклонена",
    "new": "🆕 Без доступа",
    "banned": "🚫 Забанен",
    "blacklisted": "⛔ В чёрном списке",
}

LIST_META = {
    "all": ("👥", "СПИСОК УЧАСТНИКОВ"),
    "banned": ("🚫", "ЗАБАНЕННЫЕ"),
    "black": ("⛔", "ЧЁРНЫЙ СПИСОК"),
    "staff": ("🛡", "АДМИНИСТРАЦИЯ"),
}

ACTION_VERBS = {
    "ban": "забанить",
    "kick": "кикнуть из бота",
    "black": "добавить в чёрный список",
}

ACTION_DONE = {
    "warn": "⚠️ Варн выдан",
    "unwarn": "➖ Варн снят",
    "ban": "🚫 Участник забанен",
    "unban": "✅ Участник разбанен",
    "kick": "👢 Участник кикнут",
    "black": "⛔ Добавлен в чёрный список",
    "unblack": "♻️ Убран из чёрного списка",
}

FIELD_LABELS = {
    "name": "имя",
    "nick": "ник",
    "age": "возраст",
    "hours": "часы в Rust",
    "reputation": "репутацию",
}


def members_menu_text() -> str:
    return f"{header('👥', 'УПРАВЛЕНИЕ УЧАСТНИКАМИ')}\n\nВыбери действие 👇"


def roles_menu_text() -> str:
    return (
        f"{header('🎭', 'УПРАВЛЕНИЕ РОЛЯМИ')}\n\n"
        + quote("Выдавать и снимать можно только роли ниже твоей.")
        + "\n\nНайди участника или открой список администрации 👇"
    )


def find_prompt() -> str:
    return (
        f"{header('🔍', 'ПОИСК УЧАСТНИКА')}\n\n"
        "Отправь одним сообщением:\n"
        + quote(
            "• Telegram <b>id</b>",
            "• <b>@username</b>",
            "• <b>ник</b> или <b>имя</b> (можно часть)",
            "• <b>возраст</b> числом",
        )
    )


def results_text(q: str, n: int) -> str:
    return f"{header('🔍', 'РЕЗУЛЬТАТЫ ПОИСКА')}\n\nПо запросу «{esc(q)}» найдено: <b>{n}</b>"


def not_found_text(q: str) -> str:
    return f"😕 По запросу «{esc(q)}» ничего не найдено. Попробуй другой запрос."


def list_text(kind: str, page: int, pages: int, total: int) -> str:
    icon, title = LIST_META[kind]
    text = f"{header(icon, title)}\n\nВсего: <b>{total}</b>"
    if pages > 1:
        text += f"  ·  страница {page + 1}/{pages}"
    if total == 0:
        text += "\n\nЗдесь пока пусто."
    return text


def admin_card(u) -> str:
    icon, title, _, _ = rank_info(u["hours"])
    tg = f"@{html.escape(u['username'])}" if u["username"] else "скрыт"
    warns = u["warns"]
    data_lines = [
        f"📱 Telegram: {tg}",
        f"🎂 Возраст: <b>{esc(u['age'])}</b>",
        f"⏱ Часов в Rust: <b>{esc(u['hours'])}</b>  ·  {hours_badge(u)}",
        prime_line(u),
        game_roles_line(u),
    ]
    if u["steam_id"]:
        data_lines.append(f"🎮 Steam: <a href='https://steamcommunity.com/profiles/{u['steam_id']}'>{esc(u['steam_name'])}</a>")
    data_lines += inventory_lines(u)
    data_lines.append(f"📅 В боте с: <b>{fmt_date(u['created_at'])}</b>")
    return (
        f"{header('🗂', 'КАРТОЧКА УЧАСТНИКА')}\n\n"
        f"🏷 <b>{esc(u['nick'])}</b>\n"
        f"<i>{esc(u['name'])}</i>\n"
        f"{role_badge(u['role'])}  ┃  {icon} {title}\n"
        f"{STATUS_BADGES.get(u['status'], u['status'])}\n\n"
        + section("ДАННЫЕ", *data_lines)
        + "\n\n"
        + section(
            "РЕПУТАЦИЯ",
            f"⭐ Рейтинг: <b>{signed(u['reputation'])}</b>",
            f"{warn_icon(warns)} Варны: {bar(min(warns, 3) / 3, 3)} <b>{warns}/3</b>",
        )
        + f"\n\n🆔 <code>{u['tg_id']}</code>"
    )


def confirm_text(action: str, u) -> str:
    return (
        f"{header('⚠️', 'ПОДТВЕРЖДЕНИЕ')}\n\n"
        f"Ты точно хочешь {ACTION_VERBS[action]} участника "
        f"<b>{esc(u['nick'] or u['name'] or u['tg_id'])}</b>?"
    )


def edit_menu_text(u) -> str:
    return (
        f"{header('✏️', 'ИЗМЕНЕНИЕ ДАННЫХ')}\n\n"
        f"Участник: <b>{esc(u['nick'] or u['name'] or u['tg_id'])}</b>\n"
        "Выбери, что изменить 👇"
    )


def edit_prompt(field: str) -> str:
    hints = {
        "name": "до 64 символов",
        "nick": "до 32 символов",
        "age": "число от 5 до 99",
        "hours": "целое число",
        "reputation": "целое число, можно со знаком (например -3)",
    }
    return (
        f"{header('✏️', 'НОВОЕ ЗНАЧЕНИЕ')}\n\n"
        f"Отправь новое значение: <b>{FIELD_LABELS[field]}</b>\n"
        f"<i>{hints[field]}. Для отмены нажми /start</i>"
    )


def role_pick_text(u) -> str:
    return (
        f"{header('🎭', 'ВЫДАЧА РОЛИ')}\n\n"
        f"Участник: <b>{esc(u['nick'] or u['name'] or u['tg_id'])}</b>\n"
        f"Текущая роль: {role_badge(u['role'])}\n\n"
        "Выбери новую роль 👇"
    )


def target_notice(action: str, u) -> str:
    n = u["warns"]
    return {
        "warn": f"⚠️ <b>Предупреждение</b>\nТебе выдан варн. Всего варнов: <b>{n}</b>.",
        "unwarn": f"✅ Один из твоих варнов снят. Осталось: <b>{n}</b>.",
        "ban": "🚫 Ты заблокирован в боте.",
        "unban": "✅ Блокировка снята. Нажми /start, чтобы продолжить.",
        "kick": "👢 Ты исключён из бота. Подать анкету заново можно через /start.",
        "black": "⛔ Ты добавлен в чёрный список бота.",
        "unblack": "♻️ Ты убран из чёрного списка. Чтобы вернуться, подай анкету через /start.",
    }[action]


def role_notice(role: str) -> str:
    if role == "member":
        return "🎭 Твоя роль снята. Теперь ты обычный участник."
    return f"🎭 Тебе выдана роль: <b>{role_badge(role)}</b>"


# ---------- репутация, жалобы, обращения ----------

MEDALS = ["🥇", "🥈", "🥉"]


def who(u) -> str:
    text = f"<b>{esc(u['nick'] or u['name'] or u['tg_id'])}</b>"
    if u["username"]:
        text += f" (@{html.escape(u['username'])})"
    return f"{text} · <code>{u['tg_id']}</code>"


def rep_menu_text(u, left: int) -> str:
    return (
        f"{header('⭐', 'РЕПУТАЦИЯ')}\n\n"
        + quote(
            f"⭐ Твоя репутация: <b>{signed(u['reputation'])}</b>",
            f"🗳 Оценок на сегодня: <b>{left}</b>",
        )
        + "\n\nОцени участника, посмотри топ или сообщи о нарушении 👇"
    )


def rep_find_prompt(mode: str) -> str:
    what = "оценить" if mode == "vote" else "пожаловаться"
    return (
        f"{header('🔍', 'ВЫБОР УЧАСТНИКА')}\n\n"
        f"Отправь <b>id</b>, <b>@username</b> или <b>ник</b> участника, "
        f"которого хочешь {what}.\n<i>Ищу среди участников бота.</i>"
    )


def rep_pick_text(t) -> str:
    return (
        f"{header('⭐', 'ОЦЕНКА УЧАСТНИКА')}\n\n"
        f"{who(t)}\n"
        + quote(f"Текущая репутация: <b>{signed(t['reputation'])}</b>")
        + "\n\nВыбери оценку 👇"
    )


def vote_done_text(t, value: int) -> str:
    sign = "👍 +rep" if value > 0 else "👎 -rep"
    return f"{header('✅', 'ОЦЕНКА ПОСТАВЛЕНА')}\n\n{sign} → {who(t)}"


def rep_received_text(giver, value: int) -> str:
    sign = "👍 <b>+rep</b>" if value > 0 else "👎 <b>-rep</b>"
    return f"⭐ Тебе поставили {sign} от <b>{esc(giver['nick'] or giver['name'])}</b>."


def top_text(rows, rank: int, my_rep: int) -> str:
    lines = []
    for i, r in enumerate(rows):
        mark = MEDALS[i] if i < 3 else f"{i + 1}."
        lines.append(f"{mark} <b>{esc(r['nick'] or r['name'] or r['tg_id'])}</b> — {signed(r['reputation'])}")
    body = quote(*lines) if lines else "Пока никого нет."
    return f"{header('🏆', 'ТОП РЕПУТАЦИИ')}\n\n{body}\n\n📍 Твоё место: <b>#{rank}</b> ({signed(my_rep)})"


def report_prompt(t) -> str:
    return (
        f"{header('🚨', 'ЖАЛОБА')}\n\n"
        f"Участник: {who(t)}\n\n"
        "Опиши причину жалобы одним сообщением (до 500 символов).\n"
        "<i>Для отмены нажми «Отмена» или /start</i>"
    )


def complaint_sent_text() -> str:
    return f"{header('✅', 'ЖАЛОБА ОТПРАВЛЕНА')}\n\nАдминистрация рассмотрит её и сообщит о решении."


def complaint_card(cid: int, frm, target, text: str) -> str:
    return (
        f"{header('🚨', f'ЖАЛОБА #{cid}')}\n\n"
        + quote(f"👤 От: {who(frm)}", f"🎯 На: {who(target)}")
        + f"\n\n📝 <b>Причина</b>\n{quote(esc(text))}"
    )


def complaint_result(warned: bool) -> str:
    if warned:
        return "✅ Твоя жалоба рассмотрена: к нарушителю применены меры. Спасибо!"
    return "ℹ️ Твоя жалоба рассмотрена: нарушений не выявлено."


def support_prompt(reply: bool = False) -> str:
    title = "ОТВЕТ АДМИНИСТРАЦИИ" if reply else "НАПИСАТЬ АДМИНИСТРАТОРУ"
    what = "Напиши ответ" if reply else "Опиши свой вопрос или проблему"
    return (
        f"{header('✉️', title)}\n\n"
        f"{what} одним сообщением (до 1000 символов).\n"
        "<i>Для отмены нажми «Отмена» или /start</i>"
    )


def support_sent_text(ticket_id: int) -> str:
    return (
        f"{header('✅', 'ОТПРАВЛЕНО')}\n\n"
        f"Обращение <b>#{ticket_id}</b> передано администрации. "
        "Ответ придёт сюда, в этот чат."
    )


def ticket_card(ticket_id: int, u, text: str, new: bool) -> str:
    title = f"ОБРАЩЕНИЕ #{ticket_id}" if new else f"ОТВЕТ ПО ОБРАЩЕНИЮ #{ticket_id}"
    icon = "📨" if new else "↩️"
    return (
        f"{header(icon, title)}\n\n"
        + quote(f"👤 {who(u)}", f"🎭 {role_badge(u['role'])}")
        + f"\n\n💬\n{quote(esc(text))}\n\n"
        "<i>Ответь (reply) на это сообщение — ответ уйдёт пользователю.</i>"
    )


def ticket_reply_text(text: str) -> str:
    return f"{header('💬', 'ОТВЕТ АДМИНИСТРАЦИИ')}\n\n{quote(esc(text))}"


def ticket_closed_text(ticket_id: int) -> str:
    return f"🔒 Обращение <b>#{ticket_id}</b> закрыто. Если остались вопросы — напиши новое."



# ---------- оформление: ранги, полоски, секции ----------

RANKS = [
    (0, "🏖", "Пляжный голыш"),
    (30, "🪨", "Каменный бомж"),
    (80, "🪵", "Деревянный воин"),
    (150, "🏹", "Луковый стрелок"),
    (250, "🔩", "Металлоломщик"),
    (400, "🔥", "Печной барон"),
    (600, "🛠", "Верстачный подмастерье"),
    (800, "💣", "Рейдер-новичок"),
    (1000, "🎖", "Ветеран вайпа"),
    (1500, "⚒", "Мастер верстака"),
    (2000, "🔫", "Оружейник"),
    (3000, "☠️", "Рейд-лорд"),
    (4000, "🚢", "Карго-пират"),
    (5000, "🛢", "Нефтяной барон"),
    (7000, "🗿", "Хранитель монументов"),
    (10000, "🏆", "Легенда РАСТа"),
    (15000, "🌟", "Живая легенда"),
    (20000, "👻", "Бессмертный дух вайпа"),
]


def bar(ratio: float, width: int = 10) -> str:
    filled = max(0, min(width, round(ratio * width)))
    return "▰" * filled + "▱" * (width - filled)


def section(title: str, *lines: str) -> str:
    return f"<b>▸ {title}</b>\n" + "\n".join(lines)


def years(n: int) -> str:
    if 11 <= n % 100 <= 14:
        return "лет"
    return {1: "год", 2: "года", 3: "года", 4: "года"}.get(n % 10, "лет")


def rank_info(hours):
    """-> (иконка, название, (иконка след., название след., часов до него) | None, доля пути)."""
    h = int(hours or 0)
    idx = 0
    for i, (threshold, _, _) in enumerate(RANKS):
        if h >= threshold:
            idx = i
    low, icon, title = RANKS[idx]
    if idx + 1 < len(RANKS):
        high, nicon, ntitle = RANKS[idx + 1]
        return icon, title, (nicon, ntitle, high - h), (h - low) / (high - low)
    return icon, title, None, 1.0


# ---------- голосования ----------

NUMS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣"]


def polls_list_text(n: int) -> str:
    body = (
        f"Активных голосований: <b>{n}</b>.\nВыбери, чтобы проголосовать 👇"
        if n else "Сейчас нет активных голосований. Загляни позже!"
    )
    return f"{header('🗳', 'ГОЛОСОВАНИЯ')}\n\n{body}"


def poll_text(p, options, counts, my_vote, show: bool, is_open: bool) -> str:
    total = sum(counts.values())
    title = f"ГОЛОСОВАНИЕ #{p['id']}"
    blocks = []
    for i, opt in enumerate(options):
        if show:
            c = counts.get(i, 0)
            pct = round(c * 100 / total) if total else 0
            mine = "  ✅" if my_vote == i else ""
            blocks.append(f"{NUMS[i]} {esc(opt)}{mine}\n{bar(pct / 100)} <b>{pct}%</b> · {c}")
        else:
            blocks.append(f"{NUMS[i]} {esc(opt)}")
    if not is_open:
        status = "🔒 <b>Голосование завершено</b>"
    elif p["ends_at"]:
        status = f"⏳ Осталось: <b>{timeutil.time_left(p['ends_at'])}</b>"
    else:
        status = "♾ Без срока"
    text = (
        f"{header('🗳', title)}\n\n❓ <b>{esc(p['question'])}</b>\n\n"
        + "\n\n".join(blocks)
        + "\n\n"
        + quote(f"👥 Проголосовало: <b>{total}</b>", status)
    )
    if not show and is_open:
        text += "\n\n<i>Выбери вариант кнопкой ниже — результаты откроются после голосования.</i>"
    return text


def poll_announce(p) -> str:
    return (
        f"{header('🗳', 'НОВОЕ ГОЛОСОВАНИЕ')}\n\n"
        f"❓ <b>{esc(p['question'])}</b>\n\nЗаходи и голосуй 👇"
    )


def polls_admin_text() -> str:
    return f"{header('🗳', 'УПРАВЛЕНИЕ ГОЛОСОВАНИЯМИ')}\n\nСоздавай, завершай и удаляй голосования 👇"


def poll_new_question() -> str:
    return (
        f"{header('🗳', 'НОВОЕ ГОЛОСОВАНИЕ')}\n{progress(1, 3)}\n\n"
        "❓ Напиши вопрос (до 200 символов).\n<i>Для отмены нажми «Отмена» или /start</i>"
    )


def poll_new_options() -> str:
    return (
        f"{header('🗳', 'НОВОЕ ГОЛОСОВАНИЕ')}\n{progress(2, 3)}\n\n"
        "📋 Отправь варианты ответа — <b>каждый с новой строки</b>.\n"
        + quote("Минимум 2, максимум 6.", "Пример:", "Да", "Нет", "Воздержусь")
    )


def poll_duration_prompt() -> str:
    return (
        f"{header('🗳', 'НОВОЕ ГОЛОСОВАНИЕ')}\n{progress(3, 3)}\n\n"
        "⏳ На сколько запустить голосование?\n<i>После выбора оно сразу опубликуется и уйдёт в рассылку.</i>"
    )


def poll_delete_confirm(p) -> str:
    return (
        f"{header('⚠️', 'ПОДТВЕРЖДЕНИЕ')}\n\n"
        f"Удалить голосование <b>#{p['id']}</b> вместе со всеми голосами?"
    )


# ---------- мероприятия и календарь ----------

MONTHS = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
          "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]

EVENT_STEPS = [
    ("🏷", "Название мероприятия?"),
    ("📝", "Описание: что будет, правила, что взять с собой…"),
    ("🗓", "Дата и время начала.\n<i>Формат: ДД.ММ.ГГГГ ЧЧ:ММ, например 12.10.2026 20:00</i>\n🌍 Часовой пояс: {tz}"),
    ("📍", "Место или сервер.\n<i>Отправь «-», чтобы пропустить.</i>"),
]


def calendar_screen(year: int, month: int, n: int) -> str:
    today = timeutil.local_now()
    foot = "Нажми на день или выбери мероприятие ниже 👇" if n else "В этом месяце мероприятий пока нет."
    return (
        f"{header('📅', 'МЕРОПРИЯТИЯ')}\n\n"
        f"🗓 <b>{MONTHS[month - 1]} {year}</b>\n"
        "🔥 — есть мероприятие  ·  🔹 — сегодня\n"
        f"🕒 Всё время указано по <b>{timeutil.TZ_LABEL}</b> (сегодня {today:%d.%m.%Y})\n\n{foot}"
    )


def event_card(e, going_n: int, names, i_go: bool | None) -> str:
    d = timeutil.to_local(e["starts_at"])
    left = timeutil.time_left(e["starts_at"])
    info = [
        f"🗓 <b>{timeutil.WEEKDAYS[d.weekday()]}, {d:%d.%m.%Y}</b>",
        f"🕗 Начало: <b>{d:%H:%M} {timeutil.TZ_LABEL}</b>",
    ]
    if e["place"]:
        info.append(f"📍 Место: <b>{esc(e['place'])}</b>")
    info.append("🔴 Мероприятие уже прошло" if left == "уже прошло" else f"⏳ Через: <b>{left}</b>")
    info.append(f"👥 Идут: <b>{going_n}</b>")
    text = f"{header('📅', 'МЕРОПРИЯТИЕ')}\n\n<b>{esc(e['title'])}</b>\n\n" + quote(*info)
    if e["description"]:
        text += "\n\n" + section("ОПИСАНИЕ", esc(e["description"]))
    if names:
        extra = f" и ещё {going_n - len(names)}" if going_n > len(names) else ""
        text += "\n\n" + section("КТО ИДЁТ", ", ".join(esc(n) for n in names) + extra)
    if i_go:
        text += "\n\n✅ <b>Ты идёшь!</b>"
    return text


def event_new_prompt(step: int) -> str:
    icon, q = EVENT_STEPS[step - 1]
    q = q.replace("Часовой пояс: {tz}", f"Время указывается по <b>{timeutil.TZ_LABEL}</b>")
    return f"{header('📅', 'НОВОЕ МЕРОПРИЯТИЕ')}\n{progress(step, len(EVENT_STEPS))}\n\n{icon} {q}"


def event_preview(e) -> str:
    return "🔎 <b>Проверь перед публикацией</b>\n\n" + event_card(e, 0, [], None)


def event_announce(e) -> str:
    d = timeutil.to_local(e["starts_at"])
    lines = [f"🗓 <b>{timeutil.WEEKDAYS[d.weekday()]}, {d:%d.%m.%Y}</b> · {d:%H:%M} {timeutil.TZ_LABEL}"]
    if e["place"]:
        lines.append(f"📍 {esc(e['place'])}")
    return (
        f"{header('📅', 'НОВОЕ МЕРОПРИЯТИЕ')}\n\n<b>{esc(e['title'])}</b>\n\n"
        + quote(*lines) + "\n\nПодробности и запись — по кнопке 👇"
    )


def event_reminder(e) -> str:
    d = timeutil.to_local(e["starts_at"])
    return (
        f"⏰ <b>Скоро начало!</b>\n«{esc(e['title'])}» стартует в "
        f"<b>{d:%H:%M} {timeutil.TZ_LABEL}</b> — меньше чем через час."
    )


# ---------- Steam ----------


def event_cancelled(title: str) -> str:
    return f"❌ Мероприятие «{esc(title)}» отменено."


def events_admin_text() -> str:
    return f"{header('📅', 'УПРАВЛЕНИЕ МЕРОПРИЯТИЯМИ')}\n\nСоздавай и удаляй мероприятия 👇"


def event_delete_confirm(e) -> str:
    return (
        f"{header('⚠️', 'ПОДТВЕРЖДЕНИЕ')}\n\n"
        f"Удалить мероприятие <b>«{esc(e['title'])}»</b>? Записавшимся придёт уведомление об отмене."
    )


# ---------- категории статистики админов ----------

STAT_CATEGORIES = [
    ("app_accept", "✅ Принято анкет", ("app_accept",)),
    ("app_reject", "❌ Отклонено анкет", ("app_reject",)),
    ("warn", "⚠️ Выдано варнов", ("warn",)),
    ("ban", "🚫 Банов", ("ban",)),
    ("kick", "👢 Киков", ("kick",)),
    ("black", "⛔ Добавлено в чёрный список", ("black",)),
    ("edit", "✏️ Правок данных участников", ("edit",)),
    ("roles", "🎭 Выдано и снято ролей", ("role_give", "role_take")),
    ("poll", "🗳 Создано голосований", ("poll_create",)),
    ("event", "📅 Создано мероприятий", ("event_create",)),
    ("ticket", "💬 Ответов в поддержке", ("ticket_reply",)),
    ("emergency", "🚨 Экстренных сборов", ("emergency_send",)),
    ("hours", "🔎 Проверено часов", ("hours_verify",)),
    ("fact", "💡 Добавлено фактов", ("fact_add",)),
]

def game_roles_line(u) -> str:
    keys = roles.parse_game_roles(u["game_roles"])
    if not keys:
        return "🎯 Роли в игре: <i>не выбраны</i>"
    return "🎯 Роли в игре: " + ", ".join(
        f"{roles.GAME_ROLES[k][0]} {roles.GAME_ROLES[k][1]}" for k in keys
    )


def grole_text(u) -> str:
    chosen = roles.parse_game_roles(u["game_roles"])
    lines = [f"{i} <b>{t}</b> — {d}" for i, t, d in roles.GAME_ROLES.values()]
    return (
        f"{header('🎯', 'ИГРОВЫЕ РОЛИ')}\n\n"
        f"Выбери до {roles.MAX_GAME_ROLES} ролей, которые тебе ближе всего. "
        "Нажми на роль, чтобы выбрать или убрать её.\n\n"
        + "\n".join(lines)
        + f"\n\nВыбрано: <b>{len(chosen)}/{roles.MAX_GAME_ROLES}</b>"
    )


# ---------- поиск команды ----------


def mini_profile(u, rank: int | None = None) -> str:
    icon, title, _, _ = rank_info(u["hours"])
    tg = f"@{html.escape(u['username'])}" if u["username"] else "скрыт"
    rep = f"⭐ {signed(u['reputation'])}" + (f" · 🏆 #{rank}" if rank else "")
    return (
        f"🏷 <b>{esc(u['nick'])}</b> · <i>{esc(u['name'])}</i>\n"
        f"{role_badge(u['role'])}  ┃  {icon} {title}\n"
        f"{game_roles_line(u)}\n"
        f"⏱ {esc(u['hours'])} ч {hours_badge(u)}  ·  {rep}\n"
        f"{prime_line(u)}\n"
        f"📱 {tg}"
    )


def team_menu_text() -> str:
    return (
        f"{header('🔎', 'ПОИСК КОМАНДЫ')}\n\n"
        "Подай заявку — она появится в канале, а те, кто готов к игре, нажмут «Я готов». "
        "Я сразу напишу тебе, кто откликнулся, и покажу его профиль."
    )


def team_new_prompt() -> str:
    return (
        f"{header('🔎', 'НОВАЯ ЗАЯВКА')}\n\n"
        "Опиши, кого ищешь: цель (рейд, фарм, постройка), сколько человек, "
        "когда играть, какие роли нужны (до 400 символов).\n"
        "<i>Для отмены нажми «Отмена» или /start</i>"
    )


def team_post(rid: int, u, rank: int | None, text: str) -> str:
    return (
        f"{header('🔎', 'ПОИСК КОМАНДЫ')}\n\n"
        + mini_profile(u, rank)
        + f"\n\n📝 <b>Что ищет</b>\n{esc(text)}\n\n"
        f"<i>Заявка #{rid} · нажми «Я готов», если хочешь в команду</i>"
    )


def team_published_text(rid: int) -> str:
    return (
        f"{header('✅', 'ЗАЯВКА ОПУБЛИКОВАНА')}\n\n"
        f"Заявка <b>#{rid}</b> появилась в канале. Когда кто-то откликнется, я сразу напишу тебе."
    )


def team_response_card(req, responder, rank: int | None) -> str:
    return (
        f"{header('✋', 'НОВЫЙ ОТКЛИК')}\n\n"
        f"На твою заявку <b>#{req['id']}</b> откликнулся:\n\n"
        + mini_profile(responder, rank)
        + "\n\nНапиши ему кнопкой ниже 👇"
    )


def team_joined_text(req, author, rank: int | None) -> str:
    return (
        f"{header('✅', 'ОТКЛИК ОТПРАВЛЕН')}\n\n"
        f"Ты откликнулся на заявку <b>#{req['id']}</b>. Автор получил уведомление. "
        "Вот его профиль:\n\n"
        + mini_profile(author, rank)
    )


def team_my_text(n: int) -> str:
    body = f"Открытых заявок: <b>{n}</b>" if n else "У тебя нет открытых заявок."
    return f"{header('📋', 'МОИ ЗАЯВКИ')}\n\n{body}"


def team_request_view(req, n: int, responders) -> str:
    names = ", ".join(esc(r["nick"] or r["name"]) for r in responders) or "пока никого"
    title = f"ЗАЯВКА #{req['id']}"
    return (
        f"{header('🔎', title)}\n\n"
        f"{esc(req['text'])}\n\n"
        f"✋ Откликов: <b>{n}</b>\n👥 {names}"
    )


# ---------- экстренный сбор ----------


def emergency_prompt() -> str:
    return (
        f"{header('🚨', 'ЭКСТРЕННЫЙ СБОР')}\n\n"
        "Напиши текст сбора: что случилось и куда идти (до 500 символов). "
        "Он уйдёт всем участникам, у которых включены экстренные уведомления.\n"
        "<i>Для отмены нажми «Отмена» или /start</i>"
    )


def emergency_message(text: str, sender) -> str:
    return (
        f"🚨 <b>ЭКСТРЕННЫЙ СБОР</b> 🚨\n{LINE}\n\n"
        f"<b>{esc(text)}</b>\n\n"
        f"— {role_badge(sender['role'])} <b>{esc(sender['nick'] or sender['name'])}</b>"
    )


def emergency_preview(text: str, sender) -> str:
    return "🔎 <b>Проверь перед рассылкой</b>\n\n" + emergency_message(text, sender)


def emergency_card(e, ack_n: int, names) -> str:
    title = f"СБОР #{e['id']}"
    who_line = ", ".join(esc(n) for n in names) if names else "пока никто"
    return (
        f"{header('🚨', title)}\n\n"
        f"{esc(e['text'])}\n\n"
        f"✅ Откликнулись: <b>{ack_n}</b>\n👥 {who_line}"
    )


# ---------- факты ----------


def fact_text(tier: str, i: int, total: int, title: str, text: str) -> str:
    icon, label = TIER_LABELS[tier]
    return (
        f"{header('📚', 'ФАКТЫ О RUST')}\n\n"
        f"{icon} <b>{label}</b>\n\n"
        f"<b>{esc(title)}</b>\n{esc(text)}\n\n"
        f"<i>Факт {i + 1} из {total}</i>"
    )


# ---------- статистика админов ----------


def stat_counts(actions: dict) -> dict:
    return {key: sum(actions.get(a, 0) for a in acts) for key, _, acts in STAT_CATEGORIES}


def stats_overview(period_label: str, rows) -> str:
    lines = []
    for i, (u, total, c) in enumerate(rows, 1):
        name = esc(u["nick"] or u["name"] or u["tg_id"])
        lines.append(
            f"{i}. {ROLE_ICONS.get(u['role'], '🎮')} <b>{name}</b> — {total}"
            f"  ✅{c['app_accept']} ⚠️{c['warn']} 🚫{c['ban']}"
        )
    body = "\n".join(lines) if lines else "Пока нет данных."
    return (
        f"{header('📈', 'СТАТИСТИКА АДМИНОВ')}\n\n"
        f"🗓 Период: <b>{period_label}</b>\n\n{body}\n\n"
        "Выбери администратора, чтобы увидеть подробности 👇"
    )


def stats_detail(u, total: int, counts: dict, period_label: str) -> str:
    lines = [f"{label}: <b>{counts[key]}</b>" for key, label, _ in STAT_CATEGORIES]
    return (
        f"{header('📈', 'СТАТИСТИКА')}\n\n"
        f"{role_badge(u['role'])} <b>{esc(u['nick'] or u['name'] or u['tg_id'])}</b>\n"
        f"🗓 Период: <b>{period_label}</b>\n\n"
        + section("ДЕЙСТВИЯ", *lines)
        + f"\n\n📊 Всего действий: <b>{total}</b>"
    )


# ---------- настройки ----------


# ---------- правила сообщества ----------

RULES_MAX_LEN = 3500  # символов в готовом (HTML) тексте: в одно сообщение Telegram (4096) нужно ещё уместить заголовок

DEFAULT_RULES = (
    "<b>1. Уважение.</b> Никаких оскорблений, травли и провокаций в адрес участников и администрации.\n\n"
    "<b>2. Честность.</b> Указывай правдивые часы и данные в профиле. За обман предусмотрено наказание.\n\n"
    "<b>3. Без читов и багоюза.</b> Использование запрещённого софта и эксплойтов — бан.\n\n"
    "<b>4. Командная игра.</b> Не сливай координаты баз и планы сообщества. Договорённости внутри команды соблюдай.\n\n"
    "<b>5. Без спама и рекламы.</b> Рассылки и ссылки без согласия администрации запрещены.\n\n"
    "<b>6. Решения администрации.</b> Спорные вопросы решаются через «Написать админам», а не в чатах.\n\n"
    "<i>Это стандартный текст. Администрация может заменить его на свои правила "
    "в «Админ-меню → Настройки → Правила».</i>"
)


def rules_screen(custom: str, first_time: bool) -> str:
    """Экран правил. custom — текст, заданный админами (пусто = стандартный).
    first_time — последний шаг после обучения (с кнопкой «Согласен»)."""
    text = custom or DEFAULT_RULES
    intro = (
        "Последний шаг! Прочитай правила сообщества и подтверди, что согласен с ними 👇\n\n"
        if first_time else ""
    )
    return f"{header('📜', 'ПРАВИЛА СООБЩЕСТВА')}\n\n{intro}{text}"


def rules_admin_text(custom: str) -> str:
    text = custom or DEFAULT_RULES
    state = "✏️ свой текст" if custom else "📄 стандартный текст (ещё не менялся)"
    return (
        f"{header('📜', 'ПРАВИЛА СООБЩЕСТВА')}\n\n"
        f"Сейчас: {state}\n\n"
        f"{LINE}\n{text}\n{LINE}\n\n"
        "Так правила видят участники. Нажми «Изменить», чтобы заменить текст 👇"
    )


def rules_edit_prompt() -> str:
    return (
        f"{header('✏️', 'НОВЫЕ ПРАВИЛА')}\n\n"
        "Отправь текст правил <b>одним сообщением</b> — он полностью заменит текущий.\n"
        "Можно использовать форматирование Telegram (жирный, курсив, ссылки): оно сохранится.\n"
        f"Длина — до {RULES_MAX_LEN} символов.\n\n"
        "<i>Для отмены нажми «Отмена» или /start</i>"
    )


def rules_saved_text() -> str:
    return f"{header('✅', 'ПРАВИЛА СОХРАНЕНЫ')}\n\nУчастники увидят новый текст сразу."


def settings_text(v: dict) -> str:
    def state(x: str) -> str:
        return "🟢 включён" if x == "1" else "🔴 выключен"

    return (
        f"{header('⚙️', 'НАСТРОЙКИ БОТА')}\n\n"
        f"📝 Приём анкет: {state(v['apps_open'])}\n"
        f"⚠️ Автобан при 3 варнах: {state(v['autoban'])}\n"
        f"⭐ Оценок репутации в сутки: <b>{v['rep_per_day']}</b>\n"
        "📜 Правила сообщества — кнопка ниже\n\n"
        "Нажми на пункт, чтобы переключить или изменить 👇"
    )


# ---------- обучение новичков ----------

TUTORIAL_STEPS = [
    ("🏠", "Главное меню",
     "Здесь все разделы бота: профиль, состав, репутация, мероприятия, голосования, поиск команды, "
     "факты, правила и связь с админами.\n\nВернуться назад всегда можно кнопкой «⬅️ Назад», а команда /start "
     "откроет меню заново."),
    ("👤", "Профиль",
     "В профиле — твои данные, игровой ранг по часам, игровые роли (до 3), прайм-тайм "
     f"(когда ты играешь, время по {timeutil.TZ_LABEL}), репутация и варны.\n\n"
     "Здесь же настраиваются уведомления и привязывается Steam."),
    ("🎮", "Часы и Steam",
     "Привяжи Steam в профиле — часы подтянутся автоматически и получат отметку ✅.\n\n"
     "Можно указать часы вручную, но они будут помечены «не проверено», и админ вправе их проверить. "
     "<b>За неверные часы предусмотрено наказание по правилам.</b>"),
    ("⭐", "Репутация и жалобы",
     "Ставь +rep и -rep тем, кто этого заслужил (есть дневной лимит, себе нельзя).\n\n"
     "Видишь нарушение — пожалуйся через бота, админы разберутся. Варны копятся, "
     "при серьёзных нарушениях возможен бан."),
    ("📅", "Мероприятия и голосования",
     "В календаре дни с мероприятиями отмечены 🔥 — нажми на день или на название. "
     f"Нажми «Я пойду», и бот напомнит за час. <b>Всё время указывается по {timeutil.TZ_LABEL}.</b>\n\n"
     "В голосованиях один голос на человека."),
    ("🔎", "Команда, сборы и связь",
     "«Поиск команды» — подай заявку, и желающие нажмут «Я готов». "
     "Экстренный сбор приходит всем сразу — нажми «Иду!», если можешь.\n\n"
     "Есть вопрос — кнопка «Написать админам», ответ придёт сюда."),
]

TUTORIAL_QUIZ = [
    {
        "q": "Как откликнуться на чужую заявку в «Поиске команды»?",
        "options": ["Нажать «✋ Я готов» под заявкой в канале", "Написать админу в личку", "Ничего — бот сам подберёт"],
        "correct": 0,
        "hint": "Отклик делается кнопкой «Я готов» под заявкой.",
    },
    {
        "q": "Что будет, если указать неверные часы в Rust?",
        "options": ["Ничего, часы никто не проверяет", "Админ может наказать по правилам", "Часы исправятся сами"],
        "correct": 1,
        "hint": "Часы можно проверить, а за обман предусмотрено наказание.",
    },
    {
        "q": "По какому времени указываются мероприятия и прайм-тайм?",
        "options": ["По местному времени участника", f"По {timeutil.TZ_LABEL}", "По UTC"],
        "correct": 1,
        "hint": f"Везде используется {timeutil.TZ_LABEL}.",
    },
    {
        "q": "Можно ли поставить +rep самому себе?",
        "options": ["Да, сколько угодно", "Да, но раз в сутки", "Нет, нельзя"],
        "correct": 2,
        "hint": "Оценивать себя нельзя.",
    },
]

MONTHS_GEN = ["января", "февраля", "марта", "апреля", "мая", "июня",
              "июля", "августа", "сентября", "октября", "ноября", "декабря"]


def hours_badge(u) -> str:
    src = u["hours_source"]
    if src == "steam":
        return "✅ Steam"
    if src == "admin":
        return "✔️ проверено админом"
    return "⚠️ не проверено"


def prime_line(u) -> str:
    pt = u["prime_time"]
    if not pt:
        return "🕒 Прайм-тайм: <i>не указан</i>"
    suffix = f" {timeutil.TZ_LABEL}" if pt[:1].isdigit() else ""
    return f"🕒 Прайм-тайм: <b>{esc(pt)}</b>{suffix}"


def inventory_lines(u, dlc=None) -> list:
    lines = []
    if u["inv_updated"]:
        lines.append(f"🎨 Скинов: <b>{u['inv_items']}</b> (уникальных: {u['inv_unique']})")
    if dlc and dlc[1] and dlc[0]:
        lines.append(f"🎁 DLC: <b>{dlc[0]} из {dlc[1]}</b> <i>(со слов участника)</i>")
    return lines


def rank_level(hours) -> tuple:
    h = int(hours or 0)
    idx = 0
    for i, (threshold, _, _) in enumerate(RANKS):
        if h >= threshold:
            idx = i
    return idx + 1, len(RANKS)


def rank_block(hours) -> str:
    icon, title, nxt, ratio = rank_info(hours)
    n, total = rank_level(hours)
    if nxt:
        tail = f"{bar(ratio)} <b>{int(ratio * 100)}%</b>\nДо {nxt[0]} <b>{nxt[1]}</b> — ещё <b>{nxt[2]} ч</b>"
    else:
        tail = f"{bar(1.0)} <b>100%</b>\n🏆 Максимальный ранг достигнут!"
    return f"{LINE}\n🏅 <b>РАНГ</b> · {n}/{total}\n{icon} <b>{title.upper()}</b> {icon}\n{tail}\n{LINE}"


def owner_guest_text() -> str:
    return (
        f"{header('👑', 'ПРИВЕТ, ВЛАДЕЛЕЦ')}\n\n"
        "Сначала заполни анкету, как и все участники. Она примется автоматически, "
        "и ты сразу получишь полный доступ."
    )


def owner_accepted_text() -> str:
    return f"{header('👑', 'ГОТОВО')}\n\nАнкета сохранена. Ты владелец — полный доступ открыт!"


def tutorial_intro_text() -> str:
    return (
        f"{header('📚', 'ОБУЧЕНИЕ')}\n\n"
        "Твоя анкета принята! Пройди короткое обучение (6 шагов и 4 вопроса), "
        "затем прочитай правила сообщества — и откроются все разделы бота."
    )


def tutorial_step(i: int) -> str:
    icon, title, text = TUTORIAL_STEPS[i]
    return f"{header('📚', 'ОБУЧЕНИЕ')}\n{progress(i + 1, len(TUTORIAL_STEPS))}\n\n{icon} <b>{title}</b>\n\n{text}"


def tutorial_question(q: int) -> str:
    item = TUTORIAL_QUIZ[q]
    return (
        f"{header('🧠', 'ПРОВЕРКА ЗНАНИЙ')}\n{progress(q + 1, len(TUTORIAL_QUIZ))}\n\n"
        f"❓ <b>{item['q']}</b>"
    )


def tutorial_done_text() -> str:
    return (
        f"{header('🎓', 'ОБУЧЕНИЕ ПРОЙДЕНО')}\n\n"
        "Теперь ты полноценный участник! Все разделы открыты.\n\n"
        "💡 Начни с профиля: выбери игровые роли, укажи прайм-тайм и привяжи Steam."
    )


def prime_prompt() -> str:
    return (
        f"{header('🕒', 'ПРАЙМ-ТАЙМ')}\n\n"
        f"Когда ты обычно играешь? Время по <b>{timeutil.TZ_LABEL}</b>.\n"
        "Выбери вариант кнопкой или напиши свой, например <code>19:00-23:00</code>.\n"
        "<i>Для отмены нажми /start</i>"
    )


def day_text(year: int, month: int, day: int, n: int) -> str:
    return (
        f"{header('📅', f'{day} {MONTHS_GEN[month - 1].upper()}')}\n\n"
        f"Мероприятий в этот день: <b>{n}</b>. Выбери 👇"
    )


def steam_menu_text(u, dlc=None) -> str:
    if u["steam_id"]:
        lines = [
            f"🎮 Аккаунт: <a href='https://steamcommunity.com/profiles/{u['steam_id']}'>{esc(u['steam_name'])}</a>",
            f"⏱ Часов в Rust: <b>{esc(u['hours'])}</b>  ·  {hours_badge(u)}",
        ]
        if u["steam_synced_at"]:
            lines.append(f"🔄 Обновлено: {timeutil.fmt_short(u['steam_synced_at'])} {timeutil.TZ_LABEL}")
        lines += inventory_lines(u, dlc)
        tail = "<i>Часы обновляются автоматически раз в сутки.</i>"
        if u["hours_source"] != "steam":
            tail = (
                "⚠️ Steam не отдаёт часы. Открой в Steam: Профиль → Настройки приватности → "
                "«Данные об играх» → Публичные, затем нажми «🔄 Обновить часы»."
            )
        return f"{header('🎮', 'STEAM')}\n\n" + "\n".join(lines) + f"\n\n{tail}"
    return (
        f"{header('🎮', 'STEAM И ЧАСЫ')}\n\n"
        "Привяжи Steam — бот сам подтянет часы в Rust, они получат отметку ✅ Steam и будут "
        "обновляться раз в сутки. Заодно можно посчитать скины и отметить DLC.\n\n"
        f"Сейчас: <b>{esc(u['hours'])} ч</b> · {hours_badge(u)}\n\n"
        "<i>Привязывать необязательно: можно указать часы вручную, но тогда админ вправе их проверить. "
        "За неверные часы предусмотрено наказание по правилам.</i>"
    )


def steam_link_prompt() -> str:
    return (
        f"{header('🔗', 'ПРИВЯЗКА STEAM')}\n\n"
        "Пришли ссылку на свой профиль Steam, SteamID64 или короткое имя из ссылки.\n"
        "<i>Например: https://steamcommunity.com/id/nickname</i>"
    )


def steam_verify_prompt(code: str, name: str) -> str:
    return (
        f"{header('🔐', 'ПОДТВЕРЖДЕНИЕ STEAM')}\n\n"
        f"Нашёл аккаунт: <b>{esc(name)}</b>\n\n"
        "Чтобы подтвердить, что он твой:\n"
        "1. В Steam открой профиль → «Редактировать профиль».\n"
        f"2. В имени профиля добавь код <code>{code}</code> (например: Nick {code}).\n"
        "3. Сохрани и нажми «✅ Проверить».\n\n"
        "<i>После проверки ник можно вернуть обратно.</i>"
    )


def steam_linked_text(hours) -> str:
    if hours is None:
        return (
            f"{header('✅', 'STEAM ПРИВЯЗАН')}\n\n"
            "Аккаунт подтверждён, но Steam не отдаёт часы: «Данные об играх» скрыты.\n"
            "Открой их (Настройки приватности → «Данные об играх» → Публичные) и нажми «🔄 Обновить часы»."
        )
    return (
        f"{header('✅', 'STEAM ПРИВЯЗАН')}\n\n"
        f"Часы в Rust: <b>{hours}</b> ✅ Steam. Профиль обновлён, ранг пересчитан.\n\n"
        "Хочешь посчитать инвентарь? Скины считаются автоматически, DLC отмечаешь сам 👇"
    )


def steam_inventory_text(res: dict) -> str:
    return (
        f"{header('🎒', 'ИНВЕНТАРЬ RUST')}\n\n"
        f"🎨 Скинов всего: <b>{res['total']}</b>\n"
        f"✨ Уникальных: <b>{res['unique']}</b>\n"
        f"🛒 Можно продать на рынке: <b>{res['marketable']}</b>"
    )


def steam_dlc_text(owned: int, total: int) -> str:
    return (
        f"{header('🎁', 'DLC RUST')}\n\n"
        f"Отмечено: <b>{owned} из {total}</b>\n\n"
        "Нажимай на DLC, которые у тебя есть.\n"
        "<i>Steam не отдаёт список купленных DLC через публичный API, поэтому они указываются "
        "со слов участника. Админ может попросить подтверждение скриншотом.</i>"
    )


def manual_hours_prompt() -> str:
    return (
        f"{header('✏️', 'ЧАСЫ ВРУЧНУЮ')}\n\n"
        "Отправь количество часов в Rust числом.\n"
        "⚠️ Часы будут помечены «не проверено». <b>За неверные данные предусмотрено наказание по правилам.</b>\n"
        "<i>Для отмены нажми /start</i>"
    )


def hours_mismatch_report(u, claimed: int, real: int) -> str:
    return (
        f"{header('⚠️', 'РАСХОЖДЕНИЕ В ЧАСАХ')}\n\n"
        f"👤 {who(u)}\n"
        f"Указал вручную: <b>{claimed} ч</b>\n"
        f"По данным Steam: <b>{real} ч</b>\n\n"
        "Часы в профиле заменены на данные Steam. Решение по нарушению — за администрацией."
    )

# ---------- факты: названия уровней ----------

TIER_LABELS = {
    "novice": ("🌱", "Новичкам"),
    "mid": ("🔧", "Опытным"),
    "pro": ("💎", "Профи — знают немногие"),
}

def facts_admin_text(total: int) -> str:
    return (
        f"{header('📚', 'ФАКТЫ О RUST')}\n\n"
        "Добавляй свои факты — их увидят участники нужного уровня вместе со встроенными.\n"
        f"Добавлено вручную: <b>{total}</b>"
    )


def fact_tier_prompt() -> str:
    return f"{header('➕', 'НОВЫЙ ФАКТ')}\n\nДля какого уровня игроков этот факт? 👇"


def fact_new_prompt(tier: str) -> str:
    icon, label = TIER_LABELS[tier]
    return (
        f"{header('➕', 'НОВЫЙ ФАКТ')}\n\n"
        f"Уровень: {icon} <b>{label}</b>\n\n"
        "Отправь текст факта одним сообщением (до 600 символов).\n"
        "<i>Для отмены нажми «Отмена» или /start</i>"
    )


def fact_view_text(row) -> str:
    icon, label = TIER_LABELS[row["tier"]]
    title = f"ФАКТ #{row['id']}"
    return f"{header('📚', title)}\n\n{icon} <b>{label}</b>\n\n{esc(row['text'])}"
