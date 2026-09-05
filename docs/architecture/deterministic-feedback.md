# Deterministic live feedback (этап 10)

`services/api/app/live_feedback.py` реализует только gate и state machine для
live-cue. По умолчанию никаких cue нет. Cue может быть отправлен, только если
правило содержит `approval_state: clinically_approved`, cue входит в явный
whitelist, Signal Quality разрешает обработку, выполнен debounce и прошёл
cooldown.

Модуль не задаёт пороги ROM, темпа или качества выполнения и не создаёт текст
для пациента. Эти правила должны быть утверждены для каждого упражнения и
версионированы до подключения к WebSocket UI.

`services/api/app/deterministic_scoring.py` использует тот же принцип для
score: формула должна иметь `clinically_approved` и полный набор нормированных
компонентов. Иначе возвращается `withheld`; ML-компонент в этом модуле всегда
отсутствует.
