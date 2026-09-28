# Развёртывание QueueManager на сервере

Production-адрес проекта: `https://queuemanager.duckdns.org`.

## 1. DNS и сервер

В DuckDNS создайте поддомен `queuemanager` и укажите публичный IPv4 сервера. Запись должна открываться как `queuemanager.duckdns.org`.

На сервере должны быть доступны входящие TCP-порты `80` и `443`. UDP-порт `443` желателен для HTTP/3. Не закрывайте SSH-порт, через который выполняется настройка.

Установите Docker Engine и Docker Compose Plugin. Проверка:

```bash
docker --version
docker compose version
```

## 2. Передача проекта

Скопируйте проект на сервер, например в `/opt/queuemanager`. Не передавайте `.env`, `.venv`, локальные `*.db`, логи и папку `.audit`.

В каталоге проекта создайте production-настройки:

```bash
cd /opt/queuemanager
cp .env.production.example .env.production
openssl rand -hex 32
openssl rand -hex 32
nano .env.production
```

Первое случайное значение запишите в `POSTGRES_PASSWORD`, второе — в `SECRET_KEY`. Эти значения должны отличаться. Также укажите реальные `LEGAL_OPERATOR_NAME` и `LEGAL_CONTACT_EMAIL`.

Файл `.env.production` нельзя публиковать, отправлять в чат или добавлять в Git.

## 3. Запуск

```bash
docker compose --env-file .env.production -f docker-compose.production.yml up -d --build
docker compose --env-file .env.production -f docker-compose.production.yml ps
```

Production Compose запускает основные сервисы и один автоматический init-контейнер:

- `caddy` — принимает HTTP/HTTPS, автоматически получает и обновляет TLS-сертификат;
- `web` — QueueManager и миграции базы;
- `postgres` — постоянная база данных;
- `ollama` — локальная LLM, доступная только внутри Docker-сети.
- `ollama-model` — один раз загружает выбранную модель в серверную Ollama и после успешной загрузки завершается.

PostgreSQL, QueueManager и Ollama не публикуются напрямую в интернет. Снаружи доступны только Caddy-порты `80/443`.

## 4. Qwen в Ollama

Отдельно устанавливать Ollama или вручную загружать модель не нужно. Сервис `ollama-model` автоматически скачивает `qwen3:8b` внутрь серверного Docker volume при первом запуске production Compose.

Загрузка выполняется на сервере, а не на компьютере администратора. Модель занимает примерно 5,2 ГБ. Она хранится в отдельном Docker volume и не скачивается заново при обычном перезапуске. Пока первая загрузка не закончилась, основная работа QueueManager продолжает работать без AI.

Посмотреть ход первой загрузки можно командой:

```bash
docker compose --env-file .env.production -f docker-compose.production.yml logs -f ollama-model
```

## 5. Проверка

После того как DNS обновился и Caddy получил сертификат:

```bash
curl https://queuemanager.duckdns.org/health
docker compose --env-file .env.production -f docker-compose.production.yml logs --tail=100 web caddy
```

Ожидаемый ответ health endpoint:

```json
{"status":"ok"}
```

Создайте тестовую очередь и отсканируйте QR телефоном через мобильный интернет. В QR должен быть адрес вида `https://queuemanager.duckdns.org/q/...`.

## 6. Управление

Остановить сервис без удаления данных:

```bash
docker compose --env-file .env.production -f docker-compose.production.yml down
```

Запустить снова:

```bash
docker compose --env-file .env.production -f docker-compose.production.yml up -d
```

Обновить приложение после замены исходников:

```bash
docker compose --env-file .env.production -f docker-compose.production.yml up -d --build
```

Посмотреть логи:

```bash
docker compose --env-file .env.production -f docker-compose.production.yml logs -f
```

Не выполняйте `docker compose down -v`: параметр `-v` удаляет базу, модель Ollama и сертификаты.

## 7. Резервная копия PostgreSQL

Создать дамп:

```bash
mkdir -p backups
docker compose --env-file .env.production -f docker-compose.production.yml exec -T postgres pg_dump -U queuemanager -d queuemanager > backups/queuemanager-$(date +%F-%H%M).sql
```

Файлы резервных копий нужно регулярно копировать за пределы сервера.
