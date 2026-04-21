# UP-MVP

MVP веб-модуля формирования учебного плана для системы «Интеллектуальный методист».

Проект запускается локально на ноутбуке и состоит из:
- backend: `FastAPI + SQLAlchemy + SQLite`
- frontend: `React 18 + Vite`
- локальной LLM: `Ollama`

## Что умеет проект

- создавать учебные планы
- показывать рекомендации в Таблице 1
- редактировать структуру учебного плана в Таблице 2
- выполнять нормативные проверки в Таблице 3
- показывать пояснения ИИ-ассистента через Ollama
- экспортировать результат в `.xlsx`

## Что понадобится перед запуском

Установите заранее:
- `Python 3.11` или выше
- `Node.js 20+` и `npm`
- `Ollama`

Проверьте, что команды доступны:

```bash
python --version
node --version
npm --version
ollama --version
```

## Быстрый запуск

Если нужен самый короткий путь:

1. Склонируйте репозиторий.
2. Установите Python-зависимости.
3. Установите frontend-зависимости.
4. Запустите Ollama и скачайте модель.
5. Запустите backend.
6. Запустите frontend.
7. Откройте `http://localhost:5173`.

Ниже все шаги подробно.

## 1. Клонирование проекта

```bash
git clone <URL_ВАШЕГО_РЕПОЗИТОРИЯ>
cd UP-MVP
```

Если проект передаётся архивом, просто распакуйте его и откройте папку `UP-MVP`.

## 2. Установка backend-зависимостей

Из корня проекта:

```bash
python -m venv .venv
```

### Windows PowerShell

```powershell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Windows cmd

```bat
.venv\Scripts\activate.bat
pip install -r requirements.txt
```

### Linux / macOS

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

## 3. Установка frontend-зависимостей

Из корня проекта:

```bash
cd frontend
npm install
cd ..
```

## 4. Установка и запуск Ollama

### Установка

Скачайте и установите Ollama:
- Windows / macOS: с официального сайта Ollama
- Linux: по инструкции Ollama для вашей системы

### Загрузка модели

По умолчанию проект ожидает модель:

```bash
ollama pull llama3:latest
```

Если хотите использовать другую локальную модель, можно задать переменную окружения `OLLAMA_MODEL`.

Пример для PowerShell:

```powershell
$env:OLLAMA_MODEL="llama3:latest"
```

### Запуск Ollama

Если Ollama уже запущен как приложение в системе, отдельно ничего делать не нужно.

Если нужно запустить вручную:

```bash
ollama serve
```

Проверить, что Ollama работает:

```bash
ollama list
```

## 5. Запуск backend

Из корня проекта:

```bash
uvicorn backend.main:app --reload
```

Backend будет доступен по адресу:

```text
http://127.0.0.1:8000
```

При первом запуске backend:
- создаст SQLite-базу `up_mvp.db`
- создаст таблицы
- загрузит seed-данные из `backend/seed/`

### Проверка backend

Откройте:

```text
http://127.0.0.1:8000/api/v1/health
```

Ожидаемый ответ:

```json
{
  "data": {
    "status": "ok"
  }
}
```

## 6. Запуск frontend

В отдельном терминале:

```bash
cd frontend
npm run dev
```

Frontend будет доступен по адресу:

```text
http://localhost:5173
```

Важно:
- Vite уже настроен на proxy `/api` -> `http://localhost:8000`
- backend должен быть запущен раньше frontend или одновременно с ним

## Порядок запуска каждый раз

После первой установки обычно достаточно:

1. Запустить Ollama
2. Активировать виртуальное окружение
3. Запустить backend
4. В отдельном окне запустить frontend

Для Windows PowerShell это обычно выглядит так:

### Терминал 1

```powershell
cd UP-MVP
.venv\Scripts\Activate.ps1
uvicorn backend.main:app --reload
```

### Терминал 2

```powershell
cd UP-MVP\frontend
npm run dev
```

### Терминал 3

```powershell
ollama serve
```

Если Ollama уже работает в фоне, третий терминал не нужен.

## Как проверить, что всё запустилось

1. Откройте `http://localhost:5173`
2. Создайте новый учебный план
3. Откройте Таблицу 1 или Таблицу 2
4. Перейдите в Таблицу 3 и попробуйте выполнить проверку
5. Откройте ИИ-ассистента

Если всё в порядке:
- страницы открываются без ошибок
- планы создаются
- таблицы заполняются
- проверки работают
- ИИ-ассистент отвечает через Ollama

## Что хранится локально

- SQLite-база проекта: `up_mvp.db`
- seed-данные: `backend/seed/`
- frontend-зависимости: `frontend/node_modules/`
- Python-окружение: `.venv/`

Никакой внешний сервер БД не нужен.

## Полезные команды

### Backend-тесты

```bash
python -m pytest tests -q
```

### Демонстрационный сценарий

```bash
python -m pytest tests/test_demo_flow.py -q
```

### Production-сборка frontend

```bash
cd frontend
npm run build
```

## Переменные окружения

Проект может работать без дополнительных переменных, но при необходимости поддерживает:

- `DATABASE_URL` — строка подключения к БД
- `OLLAMA_BASE_URL` — адрес Ollama, по умолчанию `http://localhost:11434`
- `OLLAMA_MODEL` — модель Ollama, по умолчанию `llama3:latest`
- `OLLAMA_TIMEOUT` — таймаут запроса к Ollama в секундах

Пример для PowerShell:

```powershell
$env:OLLAMA_MODEL="llama3:latest"
$env:OLLAMA_TIMEOUT="180"
uvicorn backend.main:app --reload
```

## Если что-то не запускается

### 1. Не запускается `Activate.ps1`

В PowerShell может мешать политика выполнения скриптов.

Варианты:
- использовать `cmd` вместо PowerShell
- временно разрешить запуск скриптов в текущей сессии:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
```

После этого снова:

```powershell
.venv\Scripts\Activate.ps1
```

### 2. `npm` не запускается в PowerShell

Иногда PowerShell блокирует `npm.ps1`.

Самый простой вариант:

```powershell
cmd /c npm run dev
```

или

```powershell
cmd /c npm install
```

### 3. ИИ-ассистент не отвечает

Проверьте:
- установлен ли Ollama
- запущен ли Ollama
- скачана ли модель `llama3:latest`

Команды для проверки:

```bash
ollama --version
ollama list
```

Если модели нет:

```bash
ollama pull llama3:latest
```

### 4. Порт `8000` или `5173` уже занят

Либо завершите процесс, который использует порт, либо запустите сервис на другом порту вручную.

Но по умолчанию проект настроен именно на:
- backend: `8000`
- frontend: `5173`

Если меняете backend-порт, не забудьте поменять proxy в `frontend/vite.config.js`.

### 5. Ошибки при первом запуске после старой версии проекта

Если структура БД устарела, проще всего удалить локальную SQLite-базу и дать проекту создать её заново:

```text
up_mvp.db
```

Удаляйте этот файл только если вам не нужно сохранять текущие локальные данные.

## Структура проекта

```text
UP-MVP/
├── backend/                # FastAPI backend
├── frontend/               # React + Vite frontend
├── tests/                  # backend-тесты
├── requirements.txt        # Python-зависимости
├── up_mvp.db               # локальная SQLite база
└── README.md
```

## Важные особенности предметной области

- `competencies.json` в MVP моделирует перечень компетенций, пришедший из ОПОП ТИУ
- для ТИУ в текущем сценарии используются `УК`, `ОПК` и `ПКС`
- для `ПКС` автоподбор в Таблице 1 не применяется, пользователь работает вручную в Таблице 2
- `hours` вычисляется автоматически из з.е. и не вводится пользователем вручную
- нормативные проверки выполняются детерминированно в backend
- LLM не считает нормативы и не меняет план автоматически, а только даёт пояснения

## Импорт PDF в seed JSON

Это не нужно для обычного запуска проекта, но нужно для пересборки seed-данных из PDF.

Входные директории:
- `backend/seed/poop_pdf/`
- `backend/seed/best_practices_pdf/`

Быстрый запуск:

```bash
python scripts/import_poop_pdf.py
```

Расширенный запуск:

```bash
python -m backend.modules.seed_ingest.poop_pdf_importer --poop-dir backend/seed/poop_pdf --best-practices-dir backend/seed/best_practices_pdf --output backend/seed/poop_disciplines.json --report backend/seed/poop_import_report.json --manifest backend/seed/poop_import_manifest.json --review-dir backend/seed/poop_review_dump
```

## Коротко: что открыть после запуска

- frontend: `http://localhost:5173`
- backend health-check: `http://127.0.0.1:8000/api/v1/health`
- backend docs: `http://127.0.0.1:8000/docs`

