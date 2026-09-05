# Локальная среда разработки

## Назначение

Эта среда создаёт технический стенд PHOENIX. Она не предназначена для
пациентских данных, клинического применения или пилота.

Состав из `infra/docker-compose.yml`:

- PostgreSQL, Redis и MinIO для будущего хранения;
- API с `/healthz` и development-эндпоинтом `/api/v1/demo`;
- две статические веб-страницы: пациент (`localhost:8080`) и врач
  (`localhost:8081`);
- gateway, который пишет в лог только повторяющийся synthetic replay;
- health-only placeholder biomechanics;
- профиль `llm` с ai-orchestrator и локальным Ollama без заранее скачанной
  модели.

## Запуск

В корне репозитория:

```powershell
Copy-Item .env.example .env
docker compose --env-file .env -f infra/docker-compose.yml up --build
```

После запуска откройте `http://localhost:8080` или `http://localhost:8081`.
Проверки API: `http://localhost:8000/healthz` и
`http://localhost:8000/api/v1/demo`.

Остановка с сохранением dev-volumes:

```powershell
docker compose --env-file .env -f infra/docker-compose.yml down
```

LLM-профиль намеренно отключён по умолчанию: образ Ollama велик и не нужен
для текущего scaffold. Для его запуска используйте:

```powershell
docker compose --env-file .env -f infra/docker-compose.yml --profile llm up --build
```

## Seed-данные и ограничение безопасности

Миграция `services/api/migrations/versions/0001_bootstrap.sql` добавляет одну
демо-организацию, врача, пациента, synthetic protocol и replay session из 15
кадров. Запись имеет `origin=synthetic` и `validation_status=synthetic`.
Она не является измерением пациента, не используется для score, feedback,
alert, medical summary или validation.

Stage 1 всё ещё ожидает реальную обезличенную запись BLE-пакетов и официальную
спецификацию датчика. До их получения gateway не подключается к hardware.
