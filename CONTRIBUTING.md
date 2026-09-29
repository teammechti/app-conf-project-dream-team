# Правила работы в команде

## Стратегия ветвления

Команда использует **GitFlow**.

Основные долгоживущие ветки:

- `main` — стабильная версия приложения;
- `develop` — интеграционная ветка, в которую попадают готовые изменения перед выпуском.

Рабочие ветки:

- `feature/*` — новая функциональность;
- `bugfix/*` — исправление ошибок;
- `release/*` — подготовка релиза;
- `hotfix/*` — срочное исправление стабильной версии.

### Схема ветвления

```text
                           hotfix/*
                         /          \
main        ●───────────●────────────●──────────●
             \                       ↑
              \                     /
develop       ●────●────●────●─────●───────────●
               \      \       \
                \      \       \
feature/*        ●──●   ●──●    \
                              release/*
```

Основной процесс разработки:

```text
develop
   |
   +---- feature/<название>
   |          |
   |          +---- Pull Request ----> develop
   |
   +---- bugfix/<название>
              |
              +---- Pull Request ----> develop
```

Изменения в `main` и `develop` вносятся только через Pull Request.

## Правила именования веток

Имя ветки записывается в нижнем регистре. Слова разделяются дефисом.

Шаблоны:

```text
feature/<краткое-название>
bugfix/<краткое-название>
release/<версия>
hotfix/<краткое-название>
docs/<краткое-название>
```

Примеры:

```text
feature/version-endpoint
feature/ticket-status
bugfix/health-response
release/0.2.0
hotfix/startup-error
docs/contributing-rules
```

Для новой функциональности ветка создаётся от актуальной `develop`:

```bash
git checkout develop
git pull origin develop
git checkout -b feature/<название>
```

После завершения работы открывается Pull Request из `feature/*` в `develop`.

## Правила коммитов

Используем Conventional Commits.

Допустимые типы:

- `feat:` — новая функциональность;
- `fix:` — исправление ошибки;
- `docs:` — изменение документации;
- `style:` — форматирование без изменения поведения;
- `refactor:` — рефакторинг;
- `test:` — добавление или изменение тестов;
- `chore:` — инфраструктура, зависимости и служебные изменения.

Формат:

```text
<тип>: <краткое описание>
```

Примеры из репозитория:

```text
docs: add pull request template
docs: add branching and code review rules to CONTRIBUTING
```

Сообщение должно кратко отвечать на вопрос: «Что изменяет этот коммит?».

## Регламент Code Review

Каждое изменение в защищённых ветках `main` и `develop` проходит через Pull Request.

Правила:

1. Автор PR назначает минимум одного ревьюера из участников команды.
2. Автор не может одобрить собственный Pull Request.
3. Срок первого ответа ревьюера — не более **24 часов** после назначения.
4. Ревьюер проверяет изменение по чек-листу Pull Request и критериям approval ниже.
5. Замечания к коду оставляются комментариями к конкретным строкам.
6. Автор отвечает на каждый комментарий:
   - исправляет код;
   - либо объясняет, почему изменение не требуется.
7. После новых коммитов необходимо повторно проверить изменившийся код.
8. Все обсуждения должны быть закрыты через `Resolve conversation` до merge.
9. Если после двух циклов review команда не может прийти к решению, вопрос выносится на обсуждение команды.

## Критерии Approval

Ревьюер ставит **Approve** только если выполнены все условия:

1. Чек-лист автора Pull Request заполнен.
2. Название ветки соответствует правилам из раздела «Правила именования веток».
3. Коммиты оформлены в формате Conventional Commits.
4. В diff отсутствуют `.env`, пароли, токены, API-ключи и другие секреты.
5. Изменение соответствует описанию Pull Request.
6. Приложение запускается локально.
7. `GET /health` возвращает HTTP 200.
8. Существующие эндпоинты не сломаны.
9. Документация обновлена, если изменение влияет на поведение приложения.
10. Все комментарии предыдущих циклов review получили ответ и закрыты.

Если хотя бы один обязательный пункт не выполнен, ревьюер использует **Request changes** и указывает причину.

Минимальное количество approval для merge:

```text
1 approval
```

## Разрешение конфликтов в коде

Если Pull Request конфликтует с `develop` или `main`, автор сначала синхронизирует свою ветку.

Для feature-ветки:

```bash
git checkout feature/<название>
git fetch origin
git merge origin/develop
```

Для ветки, которая должна быть объединена непосредственно с `main`:

```bash
git checkout <название-ветки>
git fetch origin
git merge origin/main
```

Git покажет конфликтующие файлы.

В файле необходимо найти маркеры:

```text
<<<<<<<
=======
>>>>>>>
```

Нужно оставить правильный вариант содержимого и удалить маркеры конфликта.

После этого:

```bash
git add <файл>
git commit -m "merge: resolve conflict"
git push
```

После появления нового коммита предыдущий approval может быть сброшен правилами защиты веток. В таком случае автор нажимает **Re-request review**, а ревьюер проверяет изменения заново.

Для разрешения конфликтов запрещено использовать `git push --force` в защищённые ветки.

### Спорные решения внутри команды

Если участники не могут договориться по техническому решению:

1. Обсуждаем варианты внутри команды.
2. Проводим голосование.
3. Решение принимается большинством голосов.
4. Если команда не может принять решение самостоятельно — обращаемся к преподавателю.

## Защита веток

В репозитории настроены два активных ruleset:

```text
protect-main
protect-develop
```

### Ветка `main`

Для `main` включены:

- Restrict deletions;
- Block force pushes;
- Require a pull request before merging;
- Required approvals: 1;
- Dismiss stale pull request approvals when new commits are pushed;
- Require conversation resolution before merging.

Прямой push в `main` запрещён.

Фактическая проверка защиты:

```text
remote: error: GH013: Repository rule violations found for refs/heads/main.
remote:
remote: - Changes must be made through a pull request.
remote:
! [remote rejected] main -> main (push declined due to repository rule violations)
```

Проверка force-push:

```text
remote: error: GH013: Repository rule violations found for refs/heads/main.
remote:
remote: - Cannot force-push to this branch
remote:
remote: - Changes must be made through a pull request.
```

### Ветка `develop`

Для `develop` включены:

- Restrict deletions;
- Block force pushes;
- Require a pull request before merging;
- Require conversation resolution before merging;
- Required approvals: 1.

Запрет удаления ветки проверен командой:

```bash
git push origin --delete develop
```

GitHub отклонил операцию:

```text
remote: error: GH013: Repository rule violations found for refs/heads/develop.
remote:
remote: - Cannot delete this branch
```

> TODO (модуль 3, практика №5): после появления CI-пайплайна включить в ruleset `protect-main`
> правило `Require status checks to pass` и добавить в список обязательных проверок джобы
> линтера и тестов. До этого момента зелёный пайплайн не является условием merge.

## Встречи команды

- Частота встреч: **2 раза в неделю**.
- Канал связи: Telegram — https://t.me/+Z4ZsQro-ArhjMDk6
- Ожидаемое время ответа на сообщения: **до 24 часов**.

На встречах обсуждаются:

- состояние текущих задач;
- открытые Pull Request;
- технические проблемы;
- конфликты и блокирующие задачи;
- план работы до следующей встречи.

## Контакты команды

- **Иван** — Team Lead — Telegram: `@krasolo`
- **Олег** — Tech Lead — Telegram: `@Ole_eeee`
- **Егор** — DevOps — Telegram: `@eeggooorr`
- **Алексей** — Backend Developer — Telegram: `@tretiks856`
- **Иван** — Backend Developer — Telegram: `@krasolo`

По вопросам организации работы и распределения задач обращаться к Team Lead.

По вопросам архитектуры и технических решений — к Tech Lead.

По вопросам инфраструктуры и окружения — к DevOps.

По вопросам backend-разработки — к Backend Developer.
