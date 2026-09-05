# PHOENIX

Технический монорепозиторий для MVP веб-платформы реабилитации после primary
TKA. Проект находится на стадии инфраструктурного scaffolding и **не является
медицинским изделием или клинически готовым сервисом**.

## Быстрый запуск dev-стенда

Требуется Docker Desktop с Docker Compose.

```powershell
Copy-Item .env.example .env
docker compose --env-file .env -f infra/docker-compose.yml up --build
```

Страницы демо:

- пациент: `http://localhost:8080`;
- врач: `http://localhost:8081`;
- API: `http://localhost:8000/docs`.

Seed содержит одну организацию, врача, пациента, protocol и IMU session.
Последняя построена только из 15 synthetic replay-кадров. Она не несёт
клинического смысла, не используется для score, feedback или alerts.

Локальная LLM-контейнеризация находится в опциональном профиле `llm`: `docker
compose --env-file .env -f infra/docker-compose.yml --profile llm up --build`.
Модель не загружается автоматически и LLM пока не вызывается.

Подробности и безопасностные ограничения: [локальная среда](docs/architecture/local-development.md),
[аудит IMU](docs/imu/current-script-audit.md),
[synthetic replay](docs/imu/synthetic-replay.md) и
[protocol engine](docs/architecture/protocol-engine.md),
[gateway transport](docs/imu/gateway-transport.md).

## Локальные проверки

```powershell
python -m unittest discover -s services/imu-gateway/tests -v
python -m unittest discover -s services/api/tests -v
```

## Состояние работ

Этапы 1–5 подготовили безопасный synthetic replay, структуру dev-стенда,
tenant-scoped data model, RBAC и audit. Этап 5 реализует versioned protocol
engine и draft-каталог первых пяти упражнений. Этап 6 реализует dev transport
path от synthetic gateway до API, WebSocket и append-only raw chunks. Этап 7
добавляет технические статусы Signal Quality и статического окна калибровки;
они не являются score или клинической оценкой. Клиническое утверждение
инструкций, порогов и scoring formula ещё не выполнено.
