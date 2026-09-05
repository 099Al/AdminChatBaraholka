# ChatAdmin

ChatAdmin - Telegram-бот для администрирования групповых чатов. Он сохраняет входящие сообщения из групп в SQLite, классифицирует объявления, помогает находить повторы, удалять некорректные сообщения и ограничивать пользователей по правилам модерации.

## Что делает проект

- Запускает Telegram-бота на `aiogram`.
- Слушает сообщения в группах и супергруппах.
- Сохраняет в SQLite текст сообщения, хеш текста, хеш фото, дату, автора, альбомы, ответы и результаты классификации.
- Позволяет главному администратору привязать группу командой `/bind`.
- Через меню бота запускает проверки, рассылки, удаления и блокировки.
- Ведет счетчики нарушений: неверный формат объявлений, флуд, перелимит и повторы.
- Ограничивает пользователей read-only или полностью банит тех, кому невозможно отправить уведомление.
- Содержит отдельный Telethon-скрипт для загрузки старой истории Telegram-чата в локальную БД.

Ключевые слова задаются в [src/constants.py](src/constants.py):

```python
KEYWORDS = {"Цена", "Отдаю", "Бесплатно", "Самовывоз"}
```

Сообщение считается защищенным от удаления, если содержит одно из этих слов без учета регистра. Ответы на другие сообщения помечаются отдельным статусом и не попадают в выборку сообщений без ключевых слов.

## Как работает бот

1. При старте бот создает таблицы БД, настраивает меню команд и начинает polling.
2. Пользователь может написать `/get_id`, чтобы узнать свой Telegram user ID.
3. Главный администратор пишет в группе `/bind`, чтобы привязать эту группу к своему Telegram ID.
4. Бот сохраняет новые сообщения группы в таблицу `messages`.
5. Когда пользователь нажимает кнопку меню, бот берет привязанную группу и выполняет выбранное действие через Telegram Bot API.
6. После успешного удаления запись также удаляется из локальной БД.

Для удаления сообщений бот должен быть администратором группы с правом `Delete messages`. Для ограничений и банов нужны права `Restrict/Ban users`.

## Данные

По умолчанию в режиме разработки база создается в:

```text
data/bot.db
```

В production-режиме используется путь:

```text
/app/data/bot.db
```

URL базы можно переопределить переменной окружения `DB_URL`.

Основные таблицы:

- `messages` - сохраненные сообщения групп.
- `message_full_texts` - полный текст сообщений.
- `message_types` - справочник типов сообщений.
- `message_error_types` - справочник возможных ошибок.
- `message_errors` - найденные ошибки конкретных сообщений.
- `user_chat_bindings` - связь пользователя с активной группой, выбранной через `/bind`.
- `admins` - дополнительные пользователи, которым разрешено управлять удалением через бота; хранит `user_id`, `username`, `full_name` и дату добавления.
- `user_banned` - нарушения и блокировки пользователей; хранит счетчики `invalid_ads_count`, `flood_count`, дату последней рассылки `format_notice_sent_at`, тип причины блокировки `block_type`, срок `blocked_until` и статус `is_blocked`.

В `messages.approved` хранится результат ручной проверки: `0` — сообщение ещё
нужно проверить, `1` — решение уже принято. При изменении сообщения значение
автоматически сбрасывается в `0` вместе с результатами классификации.

## Переменные окружения

Проект читает настройки из `.env` через `pydantic-settings`.

Минимальный пример:

```env
# Telegram Bot API token from @BotFather.
BOT_TOKEN=telegram_bot_token

# Runtime mode. DEV stores SQLite in ./data/bot.db, PROD stores it in /app/data/bot.db.
ENV=DEV

# Main bot administrator Telegram user_id. Use /get_id in the bot to get it.
MAIN_ADMIN_USER=123456789

# Number of days to keep saved messages.
MESSAGE_RETENTION_DAYS=7

# Number of unclassified messages processed per classifier run.
PROCESS_MESSAGE=500

# Enables automatic message classification on bot startup.
ENABLE_MESSAGE_CLASSIFICATION=true

# If true, bot sends found invalid messages to admin chat for manual review.
SEND_INVALID_MESSAGES_TO_BOT=false

# Classifier backend: local, ollama, or openai.
MESSAGE_CLASSIFICATION_BACKEND=local

# Ollama endpoint and model when MESSAGE_CLASSIFICATION_BACKEND=ollama.
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=qwen3:4b

# OpenAI credentials when MESSAGE_CLASSIFICATION_BACKEND=openai.
OPENAI_API_KEY=sk-your-openai-api-key
OPENAI_MODEL=gpt-5-mini
```

Опционально:

```env
# Full SQLAlchemy database URL override.
DB_URL=sqlite+aiosqlite:///data/bot.db

# Telegram API credentials for Telethon history import.
API_ID=12345678
API_HASH=telegram_api_hash
PHONE=+79991234567

# Target group/channel and session file for Telethon history import.
TELETHON_TARGET=https://t.me/example_group
TELETHON_SESSION_NAME=data/tg_session

# Daily moderation limits and block durations.
LIMIT_MESSAGES=5
FLOOD_MESSAGES_LIMIT=10
BLOCKED_AFTER_LIMIT_DAYS=1
BLOCKED_AFTER_REPEAT_DAYS=7
BLOCKED_AFTER_FLOOD_DAYS=1
REPEAT_PERIOD=7
```

Для Docker Compose используется файл `.env`.

## Первичная настройка и работа

### 1. Подготовить `.env`

Создайте `.env` в корне проекта. Для локального запуска укажите `ENV=DEV`, чтобы база создавалась в `data/bot.db`.

```env
BOT_TOKEN=telegram_bot_token
ENV=DEV
MAIN_ADMIN_USER=123456789

API_ID=12345678
API_HASH=telegram_api_hash
TELETHON_TARGET=https://t.me/example_group
TELETHON_SESSION_NAME=data/tg_session
```

`BOT_TOKEN` берется у `@BotFather`. `MAIN_ADMIN_USER` - это Telegram user ID главного администратора бота. Его можно узнать командой `/get_id` в боте. `API_ID` и `API_HASH` берутся в кабинете Telegram: https://my.telegram.org -> `API development tools`. `PHONE` — номер аккаунта Telethon в международном формате.

Аккаунт, который будет использоваться в Telethon, должен быть участником группы из `TELETHON_TARGET`. Если группа приватная, сначала войдите в нее обычным Telegram-клиентом по invite-ссылке.

### 2. Первый запуск через Telethon

Telethon нужен, чтобы загрузить старую историю группы в локальную базу. Обычный бот через `aiogram` не умеет запрашивать историю чата.

```bash
uv sync
uv run python -m src.first_messages_reader
```

При первом запуске скрипт возьмет телефон из `PHONE` в `.env` и запросит только код входа Telegram. После успешной авторизации он создаст session-файл, например:

```text
data/tg_session.session
```

Затем скрипт прочитает сообщения из `TELETHON_TARGET` за срок
`MESSAGE_RETENTION_DAYS`, сохранит их в таблицу `messages` и удалит из БД записи,
которых больше нет в Telegram.

Пример успешного результата:

```text
Saved 120 messages to database for chat_id=-1001234567890.
Skipped empty/service messages: 5.
```

### 3. Запустить бота

```bash
uv run python -m src.run
```

Бот начнет получать новые сообщения через polling и сохранять их в ту же базу. Если бот был выключен недолго, Telegram может отдать ему накопленные updates после запуска.

### 4. Привязать бота к группе

Добавьте бота в нужную группу и назначьте его администратором с правом удаления сообщений.

В этой же группе главный администратор из `MAIN_ADMIN_USER` или пользователь из таблицы `admins` отправляет команду:

```text
/bind
```

Бот ответит в группе:

```text
Группа привязана.
```

После этого бот сохранит связь между Telegram user ID пользователя и `chat_id` группы. Эта связь нужна, чтобы кнопки управления знали, какую группу чистить.

### Управление доступом

Главный администратор задается в `.env`:

```env
MAIN_ADMIN_USER=123456789
```

Только главный администратор может добавлять и удалять дополнительных админов:

```text
/admin_add 987654321
/admin_remove 987654321
/admin_list
```

В меню команд Telegram эти команды отображаются только у главного администратора. Остальные пользователи видят только `/start` и `/get_id`.

Дополнительные админы сохраняются в таблице `admins`. Перезапуск бота после `/admin_add` и `/admin_remove` не нужен.

При `/admin_add` бот пытается сохранить не только `user_id`, но и `username`/имя пользователя. Telegram отдаст эти данные только если пользователь уже доступен боту, например писал ему в личку или находится в общем чате.

### 5. Удалять сообщения в работающем боте

Откройте бота и нажмите `/start`. Он покажет клавиатуру:

- `Проверить доступ` - проверяет, есть ли у бота право удалять сообщения в привязанной группе.
- `1. Найти повторные объявления` - ищет повторы за период `REPEAT_PERIOD` и отправляет их на ручную проверку.
- `2. Удаление перелимита объявлений` - удаляет сообщения сверх `LIMIT_MESSAGES` за текущий день и добавляет пользователя в кандидаты на блокировку.
- `3. Найти некорректные сообщения` - запускает выбранный классификатор и копирует подозрительные сообщения в личный чат с ботом.
- `5. Отправить сообщения` - массово отправляет авторам некорректных объявлений уведомление о формате, не чаще одного раза в сутки на пользователя.
- `6. Удалить повторные объявления` - удаляет помеченные повторы и ограничивает их авторов read-only.
- `7. Удалить некорректные сообщения` - удаляет флуд сразу, а объявления с ошибками формата удаляет только если прошло больше двух суток и сообщение не `approved`.
- `8. Заблокировать пользователей` - применяет ограничения к кандидатам на блокировку; эта кнопка идет последней.

Эти действия разрешены пользователю из `MAIN_ADMIN_USER` и пользователям из таблицы `admins`. Остальным пользователям бот отвечает `Нет доступа.` или игнорирует `/bind` в группе.

У некорректного объявления доступны inline-кнопки `Сообщить о формате` и
`Удалить`. Первая копирует объявление автору и отправляет пояснение о правилах;
если личное сообщение отправить нельзя, бот отвечает на объявление в группе.
Обе операции увеличивают `invalid_ads_count`.

Для предполагаемого флуда доступны `Удалить` и `Оставить`: удаление увеличивает
`flood_count`, а оставленное сообщение считается проверенным и больше не
отправляется классификатору до следующего редактирования.

Если массовая рассылка не может отправить уведомление пользователю в личку,
пользователь переносится в кандидаты на блокировку с причиной `notice_failed`.
Такие кандидаты при нажатии `8. Заблокировать пользователей` банятся полностью,
без права читать группу.

Удаление работает по сообщениям, которые уже есть в локальной БД. Туда попадают:

- новые сообщения, которые увидел работающий `aiogram`-бот;
- накопленные Telegram updates после короткого простоя бота;
- старая история, загруженная через `src.first_messages_reader`.

При удалении повторов бот также добавляет автора удаленного повторного сообщения
в таблицу `user_banned`. Если пользователь уже есть в таблице, бот обновляет дату
и увеличивает `block_repeat_cnt`.

### Блокировки

Кандидаты на блокировку сортируются по приоритету:

1. Повторные объявления.
2. Флуд.
3. Перелимит объявлений.
4. Невозможность отправить уведомление пользователю.

Типы блокировки:

- `repeat` - read-only на `BLOCKED_AFTER_REPEAT_DAYS`.
- `flood` - read-only на `BLOCKED_AFTER_FLOOD_DAYS`.
- `limit` - read-only на `BLOCKED_AFTER_LIMIT_DAYS`.
- `notice_failed` - полный бан на `BLOCKED_AFTER_LIMIT_DAYS`.

При достижении `FLOOD_MESSAGES_LIMIT` пользователь становится кандидатом на
блокировку за флуд. Сама блокировка выполняется только при нажатии
`8. Заблокировать пользователей`.

## Локальный запуск

Проект рассчитан на Python 3.12 и `uv`.

```bash
uv sync
uv run python -m src.run
```

При запуске бот удаляет из Telegram и таблицы `messages` сообщения старше
`MESSAGE_RETENTION_DAYS`. Очистку можно запустить отдельно:

```bash
uv run python -m src.cleanup_old_messages
```

После синхронизации бот отправляет в OpenAI до `PROCESS_MESSAGE` ещё не
классифицированных сообщений. Повторно обработанные сообщения не отправляются;
после редактирования текста, картинки, альбома или связи с ответом классификация
сбрасывается. Классификацию можно запустить отдельно:

```bash
uv run python -m src.classifiers.openai_classifier
```

Чтобы быстро отключить автоматическую проверку при запуске основного бота:

```env
ENABLE_MESSAGE_CLASSIFICATION=false
```

Отправка найденных некорректных сообщений в личный чат с ботом управляется
отдельно:

```env
SEND_INVALID_MESSAGES_TO_BOT=false
```

При `false` классификатор по-прежнему проставляет типы и ошибки в БД, но карточки
для ручной проверки не отправляются. Для режима ручной модерации установите
значение `true`.

Это не отключает отдельную команду
`python -m src.classifiers.openai_classifier`.

Для локальной классификации без OpenAI API укажите:

```env
ENABLE_MESSAGE_CLASSIFICATION=true
MESSAGE_CLASSIFICATION_BACKEND=local
```

Доступные значения `MESSAGE_CLASSIFICATION_BACKEND`:

- `local` — регулярные выражения, без сети и расходов на API;
- `ollama` — локальная модель Ollama;
- `openai` — классификация моделью OpenAI.

Локальную проверку также можно запустить отдельно:

```bash
uv run python -m src.classifiers.local_classifier
```

Для классификации через Qwen3:4B установите Ollama, загрузите модель и выберите
backend:

```bash
ollama pull qwen3:4b
```

```env
ENABLE_MESSAGE_CLASSIFICATION=true
MESSAGE_CLASSIFICATION_BACKEND=ollama
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=qwen3:4b
```

Отдельный запуск:

```bash
uv run python -m src.classifiers.ollama_classifier
```

Перед запуском нужно создать `.env` с `BOT_TOKEN`.

## Запуск в Docker

```bash
docker compose -f deploy/docker-compose.yaml up -d --build
```

Контейнер запускает:

```bash
uv run python -m src.run
```

Папка `data` пробрасывается в контейнер как `/app/data`, чтобы SQLite-база сохранялась между перезапусками.

## Миграции

В проекте настроен Alembic:

```bash
alembic upgrade head
```

При обычном запуске бот также вызывает `Base.metadata.create_all`, поэтому таблицы создаются автоматически, если их еще нет.

## Загрузка истории чата

В [src/method/reader.py](src/method/reader.py) есть отдельный скрипт на `Telethon`, который читает историю Telegram-чата от имени пользовательского аккаунта и сохраняет сообщения в ту же SQLite-базу, что использует бот:

```bash
uv run python src/method/reader.py
```

Скрипт берет `API_ID`, `API_HASH`, `TELETHON_TARGET` и другие настройки из `.env`. При первом запуске он запросит номер телефона и код входа Telegram, после чего создаст `.session`-файл для повторного использования авторизации.

Сообщения сохраняются с `chat_id` в формате Bot API. Для супергрупп это ID вида `-100...`, поэтому после загрузки истории существующие кнопки бота могут удалять найденные сообщения по тем же `message_id`.

Важно: API-ключи, `.session`-файлы, `.env`, `.env.prod`, `history.csv` и локальную базу данных не стоит коммитить в репозиторий.

## Структура проекта

```text
src/run.py                         точка входа бота
src/check_bot.py                   проверка BOT_TOKEN и вывод ID бота
src/check_telethon.py              проверка API_ID/API_HASH и вывод user ID
src/config.py                      настройки окружения и URL базы
src/constants.py                   ключевые слова и константы
src/handlers/                      обработчики команд, кнопок и сообщений
src/database/models/               SQLAlchemy-модели
src/database/repo/repo_clean.py    запросы к базе
src/database/migrations/           Alembic-миграции
src/method/reader.py               Telethon-утилита для загрузки истории
build/Dockerfile                   Docker-образ
deploy/docker-compose.yaml         запуск контейнера
```

## Ограничения и особенности

- Бот работает только с сообщениями, которые видит после запуска и добавления в группу.
- Удаление за неделю основано на локально сохраненных сообщениях, а не на полном чтении истории Telegram.
- Повторы определяются по нормализованному короткому тексту сообщения.
- Telegram может не дать удалить некоторые сообщения, например если они уже удалены или недоступны для удаления. Такие сообщения считаются пропущенными.
