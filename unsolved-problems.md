# Нерешённые вопросы и блокеры

Дата фиксации: 2026-09-05.

## Критические внешние зависимости

1. Нет официального протокола IMU-датчиков: packet specification, checksum,
   service UUID, characteristic UUID, частота передачи, настройки диапазонов и
   допустимое число одновременных BLE-подключений. Поэтому hardware adapter не
   реализован и checksum физического пакета не может считаться подтверждённым.

2. Нет утверждённого метода калибровки: поза, длительность, анатомические оси,
   правила установки THIGH/SHANK/FOOT и критерии успешности. Текущая
   калибровка подтверждает только техническое статическое окно; она не задаёт
   анатомическую систему координат и не позволяет корректно получить угол
   колена или ROM.

3. Нет клинически утверждённых определений упражнений: допустимые ROM, темп,
   hold, valid/incomplete repetition, stop conditions, противопоказания и
   тексты live-cues. До этого нельзя реализовывать rep segmentation, score,
   feedback или рекомендации пациенту.

4. Нет размеченного набора данных с согласием пациентов: exercise labels,
   movement phases, границы повторов, ошибки, эксперт-разметчики и разбиение
   train/validation/test по пациентам. Поэтому stage-9 ML работает только в
   безопасном shadow режиме с `abstained`, без модели и без влияния на UI.

## Технические ограничения текущего dev-стенда

1. Gateway работает только с deterministic synthetic replay. Он не является
   измерением пациента и специально не проходит полноценное окно калибровки.

2. WebSocket fan-out работает in-process. Для production нужен durable broker,
   повторная доставка, горизонтальное масштабирование и observability.

3. Raw packet сейчас сохраняется как отдельный development chunk в PostgreSQL.
   Для production нужен формат пакетных raw chunks, объектное хранилище,
   retention policy, encryption и управляемый доступ к исходным данным.

4. Нет интеграционного запуска Docker Compose в текущей проверке: unit-тесты и
   lint проходят, но полный путь gateway -> API -> PostgreSQL -> WebSocket
   следует прогнать после доступности Docker Desktop и чистой базы миграций.

5. Технические пороги Signal Quality (3 секунды, 15 Hz, 100 ms skew и другие)
   являются engineering defaults. Они не валидированы для конкретной модели
   датчика или клинического использования.

6. `apps/clinician-web` на момент фиксации — статическая HTML-страница с
   единственным inline `<script>` (без `package.json`, сборки или `src/`),
   что нарушает правило раздела 2 `IMPLEMENTATION_PLAN.md` об интерактивных
   React + TypeScript UI. `apps/patient-web` этому правилу соответствует.
   Статус закрывается переделкой `apps/clinician-web` в React + TypeScript
   SPA по паттерну `apps/patient-web`.

## Что уже можно показать

1. Synthetic three-sensor replay проходит gateway transport, API и durable
   raw-event persistence.

2. Signal Quality возвращает `HIGH`, `MEDIUM`, `LOW` или `INVALID` с
   техническими причинами и блокирует downstream processing при `LOW`/
   `INVALID`.

3. Biomechanics service выполняет timestamp normalization, resampling и
   raw filtering только при открытом quality gate.

4. Relative orientation endpoint требует explicit baseline обоих датчиков и
   возвращает generic quaternion без claims о knee angle или ROM.

5. Shadow-inference endpoint возвращает versioned safe abstention и не влияет
   на score, feedback или safety rules.

## Безопасный порядок дальнейшей работы

1. Получить и задокументировать протокол реальных IMU.
2. Утвердить и провалидировать метод калибровки и mapping датчиков на
   анатомические оси.
3. Создать размеченные replay-сессии и validation report для ROM/repetitions.
4. После клинического утверждения реализовать deterministic rep segmentation
   и только затем scoring/live feedback.
5. Подготовить и валидировать локальную ML-модель в shadow mode.

## Уточнения из НТЗ версии 1.2

Источник: `PHOENIX_NTZ_TKA_v1.2.docx`, получен 2026-09-05.

1. Production patient client: нужно принять архитектурное решение между native
   приложением, Flutter/React Native и device gateway. Web-only BLE нельзя
   считать production-стратегией из-за ограничений Web Bluetooth, включая
   Safari/iOS. Текущий отдельный gateway совместим с НТЗ, но не заменяет выбор
   конечного пользовательского клиента.

2. Границы 6-axis IMU: в формулах, score и feedback допустимы только
   акселерометр и гироскоп трёх датчиков. Нельзя заявлять измерение силы,
   нагрузки на сустав, EMG, давления, camera pose, компенсаций таза/корпуса,
   bilateral gait symmetry или других отсутствующих сигналов.

3. Для MVP должен быть зафиксирован scope: взрослые пациенты после
   одностороннего primary TKA. Нужны обязательные структурированные поля:
   оперированная сторона, дата операции/POD, тип операции `primary_tka`,
   клиника/хирург, weight-bearing status, individual precautions и следующий
   визит.

4. Требуется утвердить core library из 8-10 упражнений, собственные reference
   videos и placement трёх IMU. Первой опорной exercise definition в НТЗ
   является Heel Slide; её ROM/repetitions/tempo/hold всё ещё требуют
   validation before production score.

5. Safety workflow требует отдельного клинического решения: какие ответы
   patient-reported questionnaire останавливают сессию, когда требуется
   контакт с врачом и какие действия считаются лишь поводом для review, а не
   диагнозом.

6. Для production обязательна validation programme: bench test
   синхронизации/packet loss/reconnect, comparison knee angle/ROM/repetition
   с референсным измерением, экспертная разметка качества и фиксированный
   validation report. Prototype target latency для live feedback -- менее
   300-500 ms, но final threshold зависит от выбранного hardware.

7. НТЗ §10.2 (IMU-02) рекомендует sampling 50-100 Hz, но единственное
   подтверждённое владельцем проекта железо (WitMotion WT901BLE68, см.
   `docs/imu/current-script-audit.md`) по BLE реально выдаёт только 10 или
   20 Hz в зависимости от настройки прошивки -- на порядок меньше
   рекомендации НТЗ. До bench-валидации на этой частоте нельзя закладывать
   frequency-domain/smoothness метрики (§11.4 НТЗ: PSD, dominant frequency,
   SPARC, jerk) как рабочие: при 10-20 Hz предел Найквиста (5-10 Hz) делает
   такие признаки ненадёжными для целевых движений реабилитации.

8. Действующий в коде engineering-default порог Signal Quality -- поток ниже
   технической частоты 15 Hz даёт `LOW` (`docs/imu/signal-quality.md`,
   `services/api/app/signal_quality.py`) -- несовместим с конфигурацией
   подтверждённого датчика на 10 Hz: система будет систематически
   блокировать scoring на разрешённой вендором настройке железа. Нужно
   решение до включения hardware-режима: обязать прошивку на ≥20 Hz либо
   сделать порог Signal Quality конфигурируемым по фактической частоте
   устройства. Связано с R-07 НТЗ (bench-валидация синхронизации).
