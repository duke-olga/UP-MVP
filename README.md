# UP-MVP

MVP веб-модуля формирования учебного плана для системы «Интеллектуальный методист» (ТИУ).

Проект запускается локально и состоит из:
- **backend**: `FastAPI + SQLAlchemy + SQLite`
- **frontend**: `React 18 + Vite`
- **локальная LLM**: `Ollama` (llama3 или совместимая модель)
- **RAG-контур**: ФГОС PDF + эмбеддинги (`sentence-transformers`)

## Что умеет проект

- создавать и хранить учебные планы
- показывать рекомендации по дисциплинам и практикам из ПООП и лучших практик (Таблица 1)
- переносить рекомендованные элементы в план одним действием
- редактировать структуру учебного плана: дисциплины, практики, ГИА, факультативы (Таблица 2)
- семантически искать дисциплины и подбирать компетенции по смыслу запроса
- выполнять нормативные проверки по ФГОС ВО с классификацией нарушений (critical / error / warning) (Таблица 3)
- отвечать на вопросы об учебном плане через ИИ-ассистент, опирающийся на ФГОС-документы (RAG)
- экспортировать план в `.xlsx`

## Требования к оборудованию

| Компонент | Минимум |
|-----------|---------|
| RAM | 8 ГБ (6 ГБ нужны Ollama для llama3 Q4) |
| Диск | 10 ГБ свободно (модели Ollama ~4–5 ГБ) |
| ОС | Windows 10/11, macOS 12+, Linux |
| Интернет | нужен при первом запуске для скачивания модели эмбеддингов |

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

Если хотите использовать другую локальную модель, задайте переменную окружения `OLLAMA_MODEL`.

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

## 5. Подготовка ФГОС-документов для RAG

ИИ-ассистент использует RAG (Retrieval-Augmented Generation): перед ответом он ищет
релевантные фрагменты из ФГОС ВО и опирается на них. Для этого нужны PDF-файлы ФГОС.

### Структура папки

```text
backend/seed/fgosvo/
├── 09.03.01/   # Информатика и вычислительная техника
│   └── fgos.pdf
├── 09.03.02/   # Информационные системы и технологии
│   └── fgos.pdf
├── 09.03.03/   # Прикладная информатика
│   └── fgos.pdf
└── 09.03.04/   # Программная инженерия
    └── fgos.pdf
```

Положите PDF-файл ФГОС ВО для нужного направления подготовки в соответствующую папку.
Имя файла может быть любым, важно расширение `.pdf`.

Если папка пустая или PDF отсутствует — RAG работает только на seed-данных (компетенции,
нормативы, рекомендованные дисциплины). Это допустимо, но качество ответов ИИ-ассистента
по конкретным пунктам ФГОС будет ниже.

### Модель эмбеддингов

При первом запросе к семантическому поиску или ИИ-ассистенту backend автоматически
скачивает модель эмбеддингов (`paraphrase-multilingual-MiniLM-L12-v2`, ~120 МБ).
Нужен доступ в интернет. После загрузки модель кэшируется локально.

## 6. Запуск backend

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
- загрузит seed-данные из `backend/seed/` (компетенции, ПООП-дисциплины, нормативы)

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

## 7. Запуск frontend

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
- Vite настроен на proxy `/api` → `http://localhost:8000`
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
3. Откройте Таблицу 1 — должны появиться рекомендованные дисциплины
4. Перейдите в Таблицу 3 и выполните проверку
5. Откройте ИИ-ассистент (кнопка в правом нижнем углу) и задайте вопрос

Если всё в порядке:
- страницы открываются без ошибок
- планы создаются и сохраняются
- таблицы заполняются данными
- проверки работают и выдают результаты
- ИИ-ассистент отвечает через Ollama

## Что хранится локально

- SQLite-база проекта: `up_mvp.db`
- seed-данные: `backend/seed/`
- ФГОС PDF для RAG: `backend/seed/fgosvo/`
- frontend-зависимости: `frontend/node_modules/`
- Python-окружение: `.venv/`
- кэш модели эмбеддингов: `~/.cache/huggingface/` (создаётся автоматически)

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

Проект работает без дополнительных переменных, но при необходимости поддерживает:

| Переменная | По умолчанию | Описание |
|------------|-------------|----------|
| `DATABASE_URL` | `sqlite:///./up_mvp.db` | Строка подключения к БД |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Адрес Ollama |
| `OLLAMA_MODEL` | `llama3:latest` | Модель Ollama |
| `OLLAMA_TIMEOUT` | `120` | Таймаут запроса к Ollama (секунды) |

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

### 4. Семантический поиск или RAG не работают

ИИ-ассистент и семантический поиск требуют модель эмбеддингов.
При первом запросе она скачивается автоматически (~120 МБ), нужен интернет.

Если интернета нет — скачайте модель заранее:

```bash
pip install huggingface_hub
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')"
```

Если модель есть, но ИИ всё равно не отвечает на вопросы по ФГОС — проверьте,
что в `backend/seed/fgosvo/<направление>/` лежит PDF-файл ФГОС.

### 5. Порт `8000` или `5173` уже занят

Либо завершите процесс, который использует порт, либо запустите сервис на другом порту.

Если меняете backend-порт, не забудьте поменять proxy в `frontend/vite.config.js`.

### 6. Ошибки при первом запуске после старой версии проекта

Если структура БД устарела, проще всего удалить локальную SQLite-базу и дать проекту
создать её заново:

```text
up_mvp.db
```

Удаляйте этот файл только если вам не нужно сохранять текущие локальные данные.

## Структура проекта

```text
UP-MVP/
├── backend/
│   ├── main.py                  # FastAPI приложение, запуск, миграции
│   ├── models.py                # ORM-модели (CurriculumPlan, PlanElement, ...)
│   ├── schemas.py               # Pydantic-схемы запросов и ответов
│   ├── modules/
│   │   ├── llm_explainer/       # ИИ-ассистент: адаптер Ollama, чат-сервис
│   │   ├── rag/                 # RAG-контур: chunker, retriever, ФГОС PDF-парсер
│   │   ├── recommendation/      # Семантический поиск, эмбеддинги
│   │   ├── plan_builder/        # Расчёт з.е., покрытие компетенций
│   │   ├── validation/          # Детерминированные нормативные проверки
│   │   ├── seed_ingest/         # Загрузка seed-данных из JSON
│   │   └── export/              # Экспорт в XLSX
│   └── seed/
│       ├── competencies.json    # Компетенции (УК, ОПК, ПКС)
│       ├── poop_disciplines.json # Рекомендованные дисциплины из ПООП
│       ├── normative_params.json # Нормативы ФГОС (з.е., часы, доли)
│       └── fgosvo/              # PDF-файлы ФГОС ВО для RAG
│           ├── 09.03.01/
│           ├── 09.03.02/
│           ├── 09.03.03/
│           └── 09.03.04/
├── frontend/
│   └── src/
│       ├── pages/               # Table1, Table2, Table3, PlanSetup
│       └── components/          # AiChat, CompetencyMultiSelect, ...
├── tests/                       # Backend-тесты (pytest)
├── requirements.txt             # Python-зависимости
├── up_mvp.db                    # SQLite-база (создаётся при первом запуске)
└── README.md
```

## Важные особенности реализации

- `competencies.json` в MVP моделирует перечень компетенций, пришедший из ОПОП ТИУ
- для ТИУ используются `УК`, `ОПК` и `ПКС`; для `ПКС` автоподбор в Таблице 1 не применяется
- `hours` вычисляется автоматически из з.е. (1 з.е. = 36 ч) и не вводится вручную
- нормативные проверки детерминированы: LLM не считает нормативы и не правит план автоматически
- LLM отвечает только на вопросы, используя RAG-контекст из ФГОС и текущий план; «от себя» не добавляет
- RAG-кэш сбрасывается автоматически при изменении данных в БД

## Импорт PDF в seed JSON

Это не нужно для обычного запуска, но нужно для пересборки seed-данных из PDF.

Входные директории:
- `backend/seed/poop_pdf/`
- `backend/seed/best_practices_pdf/`

Быстрый запуск:

```bash
python scripts/import_poop_pdf.py
```

Расширенный запуск:

```bash
python -m backend.modules.seed_ingest.poop_pdf_importer \
  --poop-dir backend/seed/poop_pdf \
  --best-practices-dir backend/seed/best_practices_pdf \
  --output backend/seed/poop_disciplines.json \
  --report backend/seed/poop_import_report.json \
  --manifest backend/seed/poop_import_manifest.json \
  --review-dir backend/seed/poop_review_dump
```

## Коротко: что открыть после запуска

- frontend: `http://localhost:5173`
- backend health-check: `http://127.0.0.1:8000/api/v1/health`
- backend API docs (Swagger): `http://127.0.0.1:8000/docs`
