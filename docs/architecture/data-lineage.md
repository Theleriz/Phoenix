# Data lineage и неизменяемость

## Цепочка происхождения

Каждый производный результат должен быть связан с исходными данными:

```text
patient → episode_of_care → rehab_session → exercise_attempt
  → raw_imu_chunk → calibration + algorithm_version + parameters
  → derived_metric / signal_quality → score_version → exercise_score
```

Все клинические сущности содержат `organization_id`. Фильтрацию и RBAC будет
применять API на этапе 4; наличие tenant key в схеме само по себе не является
авторизацией.

## Версии и пересчёт

`algorithm_versions`, `score_versions` и `prompt_versions` хранят точную
версию кода/формулы или prompt и параметры. `exercise_scores` не заменяется
при пересчёте: новая строка указывает `recalculated_from_score_id` и причину
в `calculation_reason`.

## Append-only данные

Триггеры PostgreSQL запрещают `UPDATE` и `DELETE` для `raw_imu_chunks`,
`exercise_scores`, `clinician_actions` и `safety_assessments`. Это
предотвращает перезапись первичных данных, результата, клинического действия
и записи о детерминированной оценке безопасности. Файлы raw-пакетов хранятся
отдельно; схема сохраняет URI и SHA-256.

Каждый `POST .../symptom-check` пишет ровно одну строку `safety_assessments`
в той же транзакции, что и `symptom_checks`, alert и audit — для любого
исхода, включая `GREEN` и `withheld`. Строка ссылается на `symptom_check_id`
и `policy_version`, поэтому повторная оценка по новой политике отличима от
исходной.

## Ограничения текущей миграции

Схема и связи технически подготовлены, но не дают clinical scoring, RBAC,
alerts или EHR-интеграцию. Seed из этапа 2 остаётся synthetic и не создаёт
медицинских результатов.
