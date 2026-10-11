# PROJECT.md — карта проекта (для разработчика и для Claude)

Telegram-бот закрытого сообщества по игре Rust. Python 3.12+, aiogram 3.x, SQLite (aiosqlite), long polling.
Язык интерфейса — русский, время везде по МСК (`TIMEZONE`, хранится в БД в UTC).

## Запуск
`pip install -r requirements.txt` → заполнить `.env` (шаблон `.env.example`) → `python main.py`.
Сервер: см. `DEPLOY.md`.

## Файлы
| Файл | Назначение |
|---|---|
| `main.py` | запуск: логи, проверка конфига, роутеры, фоновые задачи, обработчик ошибок |
| `config.py` | чтение `.env` |
| `roles.py` | роли бота и уровни доступа, игровые роли |
| `ui.py` | **все тексты и оформление** (заголовки, профиль, ранги, обучение, календарь…) |
| `timeutil.py` | время МСК/UTC, разбор дат и прайм-тайма |
| `utils.py` | `safe_edit`, фоновые рассылки `start_broadcast` |
| `steam.py` | клиент Steam Web API (часы, инвентарь, DLC) |
| `tasks.py` | фон: напоминания о мероприятиях, синхронизация Steam, бэкап БД |
| `facts_data.py` | список фактов о Rust |
| `database/db.py` | схема, миграции, все запросы |
| `middlewares/access.py` | устаревшие кнопки, бан/ЧС, режим тех. работ |
| `middlewares/home.py` | добавляет кнопку «🏠 Главное меню» (`home`) под каждое новое сообщение бота в личке |
| `keyboards/*.py` | кнопки (main, admin, profile, rep, support, events, polls, team, extras) |
| `handlers/*.py` | логика по разделам (см. ниже) |
| `deploy/`, `DEPLOY.md`, `DEPLOY_BEGET.md` | сервер: systemd, `setup_server.sh` (установка), `botctl` (управление), обновление |

## Handlers
`start` (меню, /start), `anketa` (анкета + принятие/отклонение), `tutorial` (обучение), `profile` (профиль, ник, игровые роли, прайм-тайм, уведомления), `steam` (привязка Steam, часы, инвентарь, DLC), `composition` (состав), `reputation` (+rep/-rep, топ, жалобы), `support` (обращения к админам), `events` (календарь и запись), `polls` (голосования), `team` (поиск команды), `facts` (факты по часовому рангу: novice <400 ч, mid 400–1999, pro ≥2000; админы добавляют свои), `emergency` (экстренный сбор), `admin` (админ-меню, тех. работы), `admin_manage` (участники, роли, правки), `stats` (статистика админов), `settings` (настройки), `channel` (личная ссылка на закрытый канал), `ops` (/status, /backup, /export).

## Роли и доступ
member 0 · moderator 1 · admin 2 · deputy 3 · chief_admin 4 · owner 5.
Владельцы задаются `ADMIN_IDS` в `.env`. Админ-меню: модератор+ (голосования), админ+ (участники, роли, ивенты, сбор), заместитель+ (статистика, настройки, тех. работы, /status), владелец (/backup).
Действовать можно только над ролями ниже своей.

## Статусы пользователя
`new` → `pending` (анкета на рассмотрении) → `onboarding` (анкета принята, идёт обучение) → `accepted` (полноценный участник). Также `rejected`, `banned`, `blacklisted`. Владелец принимается автоматически.

## Таблицы БД
users, applications, settings, facts_custom, admin_actions (журнал действий админов для статистики), rep_votes, complaints, tickets, ticket_msgs, polls, poll_votes, events, event_rsvp, team_requests, team_responses, emergencies, emergency_acks, steam_dlc, user_dlc.
Миграции — автоматически в `db.init()` (`USER_MIGRATIONS`, `APP_MIGRATIONS`).

## Префиксы callback_data
`menu` (назад, правит сообщение) `home` (из уведомлений, присылает меню новым сообщением) `admin` `profile` `notif:` `grole:` `prime`/`ptp:`/`pt:` `steam:` `dlc:` `rep:` `cmp:` `support`/`support:reply:` `tk:close:` `team:` `facts:` `polls`/`pl:` `events`/`ev:` `em:` `tut:`/`tutq:`/`tuta:` `app:` `channel` и админские `adm:*` (members, roles, u, ask, do, edit, ef, role, setrole, find, list, hv, polls, pl:*, events, ev:*, em, stats/stp/stu, settings/set, maint).

## Правила разработки
- Тексты — только в `ui.py`, кнопки — в `keyboards/`, логика — в `handlers/`, SQL — только в `database/db.py`.
- Пользовательский ввод в HTML-сообщения всегда через `ui.esc()`.
- Любое действие админа пишется в `db.log_action(...)` (для статистики).
- Сообщения редактируем через `utils.safe_edit`, длинные рассылки — через `utils.start_broadcast`.
- Новый раздел = новый файл в `handlers/` + `include_router` в `main.py` + кнопка в `keyboards/main.py`.

## Настройки в БД (`settings`)
`maintenance`, `apps_open`, `autoban`, `rep_per_day`.

## Надёжность данных
SQLite в режиме WAL с `synchronous=FULL`, коммит после каждой записи, корректное закрытие в `db.close()`.
`tasks.backup_loop`: проверка целостности → копия `.db` + выгрузка CSV → папка `backups/` (14 шт.) и отправка в Telegram (`BACKUP_CHAT_ID`, по умолчанию личка первого владельца).

## Известные ограничения
- DLC Rust Steam API не отдаёт: участник отмечает их сам (в профиле помечено «со слов»).
- Инвентарь (скины) считается только при открытом инвентаре Steam.
- Состояния форм хранятся в памяти (после перезапуска форму нужно начать заново).
- Кнопки в сообщениях старше 48 часов Telegram отдаёт боту как недоступные — бот просит открыть меню через /start.

## История этапов
1 анкеты, профиль, состав, тех. работы · 2 управление участниками и ролями · 3 репутация, жалобы, обращения · 4 голосования, мероприятия, календарь · 5 поиск команды, факты, экстренный сбор, статистика, настройки · 6 Steam (часы, инвентарь, DLC), прайм-тайм, обучение, ранги, МСК · 7 закрытый канал, защита от сбоев, бэкапы, деплой · 8 факты по рангам, кнопка «Главное меню» в уведомлениях, копии базы в Telegram.
