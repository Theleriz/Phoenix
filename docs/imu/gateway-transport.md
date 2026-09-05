# IMU gateway transport (этап 6)

Gateway использует `SequenceTracker` для каждого явно назначенного датчика.
Он различает пропуск sequence, duplicate и out-of-order пакет; эти события
являются техническими метаданными и не превращаются в клинический feedback.

`normalize_packet()` формирует единый outbound-контракт с `session_id`,
`device_id`, ролью `thigh`/`shank`/`foot`, gateway timestamp, sequence и raw
осями. `DurableBuffer` сохраняет неподтверждённо отправленные события в
append-only JSONL-файл и удаляет файл только после подтверждения доставки.

`deliver_packets()` отправляет события последовательно и помещает только
неподтверждённые события в buffer; `flush_buffer()` повторяет буфер строго по
порядку и сохраняет неподтверждённый tail. `HttpJsonSender` предоставляет
dependency-free HTTP(S) POST sender с bearer authentication.

Dev gateway направляет каждый replay-пакет на
`POST /api/v1/gateway/imu-packets`. API проверяет отдельный gateway bearer
token, сопоставляет сессию и зарегистрированный sensor device, затем до
рассылки сохраняет lossless payload в `gateway_packet_events` и append-only
запись `raw_imu_chunks`. В development fixture один пакет считается одним raw
chunk; `storage_uri` указывает на внутреннее durable-хранилище event. Живой
поток доступен через
`/api/v1/gateway/sessions/{session_id}/stream?token=...`. Это только
транспорт: synthetic данные не становятся measurements, score или feedback.

BLE hardware adapter намеренно не активируется до получения официального
packet protocol и UUID конфигурации датчиков. WebSocket fan-out пока
in-process, то есть предназначен только для локального dev-стенда; production
потребует durable broker.
