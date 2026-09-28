# QueueManager: инструкция по установке на сервер

Инструкция рассчитана на чистый сервер с Ubuntu 22.04 или 24.04 и публичным IPv4. Все команды ниже выполняются на сервере через SSH, кроме отдельно отмеченной команды загрузки архива.

Планируемый адрес: `https://queuemanager.duckdns.org`.

## 1. Проверить сервер

Рекомендуется иметь не меньше 4 CPU, 12 ГБ оперативной памяти и 25 ГБ свободного диска. QueueManager работает и без AI, но для локальной модели `qwen3:8b` серверу требуется достаточно памяти.

Узнать публичный IPv4 сервера:

```bash
curl -4 ifconfig.me
echo
```

Сохраните полученный IP — он понадобится в DuckDNS.

## 2. Создать адрес в DuckDNS

1. Откройте `https://www.duckdns.org`.
2. Войдите через доступный способ авторизации.
3. В разделе добавления домена введите только `queuemanager`, без `.duckdns.org`.
4. Нажмите добавление домена.
5. В поле IP созданного домена укажите публичный IPv4 сервера из шага 1 и нажмите обновление IP.
6. Итоговый адрес должен быть `queuemanager.duckdns.org`.

Если имя `queuemanager` уже занято, выберите другое. Затем запишите новое полное имя в `DOMAIN` файла `.env.production` на шаге 7.

Для обычного VPS со статическим IP этого достаточно. Если IP сервера динамический, настройте на сервере периодическое обновление DuckDNS по официальной инструкции: `https://www.duckdns.org/install.jsp`. Токен DuckDNS нельзя публиковать или добавлять в архив проекта.

Проверить, что домен указывает на сервер:

```bash
getent hosts queuemanager.duckdns.org
```

Отображаемый IP должен совпадать с публичным IP сервера. Обновление DNS иногда занимает несколько минут.

## 3. Открыть порты

Если используется UFW:

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 443/udp
sudo ufw enable
sudo ufw status
```

Также разрешите TCP `80/443` в firewall или security group панели хостинга. UDP `443` используется для HTTP/3 и желателен, но не обязателен для обычного HTTPS.

## 4. Установить Docker

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl unzip
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
sudo docker --version
sudo docker compose version
```

Обе последние команды должны вывести версии без ошибок.

## 5. Загрузить архив на сервер

На компьютере, где находится архив, выполните команду, заменив `SERVER_USER` и `SERVER_IP`:

```bash
scp QueueManager-production-0.5.1.zip SERVER_USER@SERVER_IP:/tmp/
```

Можно вместо `scp` использовать SFTP-клиент или загрузку файлов в панели хостинга.

## 6. Распаковать проект

Снова подключитесь к серверу по SSH и выполните:

```bash
sudo mkdir -p /opt/queuemanager
sudo unzip /tmp/QueueManager-production-0.5.1.zip -d /opt/queuemanager
sudo chown -R "$USER":"$USER" /opt/queuemanager
cd /opt/queuemanager
```

## 7. Создать секретные настройки

```bash
cp .env.production.example .env.production
sed -i "s/replace_with_random_hex/$(openssl rand -hex 32)/" .env.production
sed -i "s/replace_with_another_random_hex/$(openssl rand -hex 32)/" .env.production
nano .env.production
```

Проверьте в редакторе:

```env
DOMAIN=queuemanager.duckdns.org
LEGAL_OPERATOR_NAME=Название или имя владельца сервиса
LEGAL_CONTACT_EMAIL=действующая-почта@example.com
```

Если в DuckDNS было выбрано другое имя, измените `DOMAIN`. Пароли и `SECRET_KEY` после генерации не меняйте без необходимости. Сохранить файл в nano: `Ctrl+O`, `Enter`, выйти: `Ctrl+X`.

Файл `.env.production` нельзя отправлять другим людям, публиковать или добавлять в Git.

## 8. Запустить QueueManager

```bash
sudo docker compose --env-file .env.production -f docker-compose.production.yml up -d --build
```

Эта одна команда автоматически:

- скачает необходимые Docker-образы на сервер;
- запустит PostgreSQL;
- применит миграции базы;
- запустит QueueManager;
- запустит Ollama;
- скачает `qwen3:8b` внутрь серверного Docker volume;
- запустит Caddy и запросит HTTPS-сертификат для домена.

На компьютер администратора Ollama и Qwen не устанавливаются. Первая серверная загрузка модели размером около 5,2 ГБ может занять некоторое время.

## 9. Следить за первым запуском

Состояние контейнеров:

```bash
sudo docker compose --env-file .env.production -f docker-compose.production.yml ps -a
```

Ход загрузки Qwen:

```bash
sudo docker compose --env-file .env.production -f docker-compose.production.yml logs -f ollama-model
```

После успешной загрузки контейнер `ollama-model` завершится с кодом `0` — это нормально. Выйти из просмотра логов: `Ctrl+C`.

Логи сайта и HTTPS:

```bash
sudo docker compose --env-file .env.production -f docker-compose.production.yml logs --tail=100 web caddy
```

## 10. Проверить сайт

```bash
curl https://queuemanager.duckdns.org/health
```

Правильный ответ:

```json
{"status":"ok"}
```

Откройте в браузере `https://queuemanager.duckdns.org`, зарегистрируйте организатора и проверьте:

1. Создание очереди.
2. AI-заполнение формы.
3. Вход участника.
4. Сканирование QR-кода телефоном через мобильный интернет.
5. Обновления очереди в реальном времени.

QR должен вести на адрес вида `https://queuemanager.duckdns.org/q/...`.

## 11. Обычное управление

Посмотреть состояние:

```bash
cd /opt/queuemanager
sudo docker compose --env-file .env.production -f docker-compose.production.yml ps -a
```

Посмотреть логи:

```bash
sudo docker compose --env-file .env.production -f docker-compose.production.yml logs -f
```

Перезапустить:

```bash
sudo docker compose --env-file .env.production -f docker-compose.production.yml restart
```

Остановить без удаления данных:

```bash
sudo docker compose --env-file .env.production -f docker-compose.production.yml down
```

Запустить снова:

```bash
sudo docker compose --env-file .env.production -f docker-compose.production.yml up -d
```

Никогда не используйте `docker compose down -v`, если данные ещё нужны: `-v` удалит базу, модель и сертификаты.

## 12. Резервная копия

```bash
cd /opt/queuemanager
mkdir -p backups
sudo docker compose --env-file .env.production -f docker-compose.production.yml exec -T postgres pg_dump -U queuemanager -d queuemanager > "backups/queuemanager-$(date +%F-%H%M).sql"
```

Резервные копии нужно регулярно сохранять за пределами сервера.

## Если сайт не открылся

Проверьте по порядку:

```bash
getent hosts queuemanager.duckdns.org
sudo docker compose --env-file .env.production -f docker-compose.production.yml ps -a
sudo docker compose --env-file .env.production -f docker-compose.production.yml logs --tail=200 caddy web
sudo ss -lntup | grep -E ':80|:443'
```

Частые причины: DuckDNS указывает не на тот IP, закрыты порты `80/443`, домен ещё не обновился или другой сервис уже занял порты.
