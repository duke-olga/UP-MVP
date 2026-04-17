# UP-MVP

MVP модуля формирования учебного плана.

## Backend

Требования:
- Python 3.11+

Установка зависимостей:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Запуск backend:

```bash
uvicorn backend.main:app --reload
```

Проверка health-check:

```bash
curl http://127.0.0.1:8000/api/v1/health
```

Ожидаемый ответ:

```json
{"status":"ok"}
```
