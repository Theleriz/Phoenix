# Protocol engine (этап 5)

Конфигурация упражнения хранится в `exercise_definitions.configuration`, а
назначение пациента — в `exercise_prescriptions.configuration`. Условия
упражнений не зашиваются в обработчиках API.

В MVP каталог первых пяти упражнений создаётся миграцией
`0005_exercise_catalog.sql`: Heel Slide, Short Arc Quad, Ankle Pumps, Straight
Leg Raise и Prone Knee Bend. Новые записи имеют состояние `draft`, потому что
клинические инструкции, пороги и scoring formula требуют отдельного утверждения.

При изменении назначения создаётся новый `protocol_assignment` с увеличенной
версией. Предыдущая версия получает `superseded_at`, но не изменяется. Список
упражнений и история доступны через:

- `GET /api/v1/exercise-definitions`;
- `GET /api/v1/episodes/{episode_id}/protocol` — текущая версия;
- `GET /api/v1/episodes/{episode_id}/protocol-history` — все версии;
- `POST /api/v1/episodes/{episode_id}/protocol-versions` — новая версия.

Ограничения применяются в порядке `phoenix_base_template` →
`clinic_or_surgeon_template` → `individual_clinician`; итоговая конфигурация
сохраняет `restriction_sources` для объяснимости. Контракты и проверка формы
находятся в `packages/contracts/protocol.py`.
