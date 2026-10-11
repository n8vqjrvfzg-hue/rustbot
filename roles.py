# role -> (название, уровень доступа)
ROLES = {
    "member":      ("Участник", 0),
    "moderator":   ("Модератор", 1),
    "admin":       ("Администратор", 2),
    "deputy":      ("Заместитель", 3),
    "chief_admin": ("Главный админ", 4),
    "owner":       ("Владелец", 5),
}


def level(role: str | None) -> int:
    return ROLES.get(role or "member", ("", 0))[1]


def title(role: str | None) -> str:
    return ROLES.get(role or "member", ("Участник", 0))[0]


# ---------- игровые роли (выбираются в профиле) ----------
MAX_GAME_ROLES = 3

GAME_ROLES = {
    "combat":   ("⚔️", "Комбатер",   "PvP-бои и перестрелки"),
    "raider":   ("💣", "Рейдер",     "штурм и вскрытие баз"),
    "farmer":   ("⛏", "Фармер",     "добыча ресурсов и лут"),
    "grower":   ("🌾", "Фермер",     "растения, гены, еда"),
    "builder":  ("🏗", "Строитель",  "базы и укрепления"),
    "crafter":  ("🔧", "Крафтер",    "снаряжение и оружие"),
    "electric": ("⚡", "Электрик",   "электричество, турели, ловушки"),
    "scout":    ("🔭", "Разведчик",  "поиск врагов и информация"),
}


def parse_game_roles(raw: str | None) -> list[str]:
    return [k for k in (raw or "").split(",") if k in GAME_ROLES]
