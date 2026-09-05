# Shadow inference (этап 9)

Инфраструктура этапа 9 изолирована в `services/biomechanics/shadow.py`.
Она требует открытый Signal Quality gate, версию модели и версии признаков.
Пока валидированная локальная модель отсутствует, результат всегда
`abstained` с фиксированной причиной. Это намеренное безопасное поведение.

Когда появится модель, её inference adapter должен сохранить версию, label,
confidence и feature versions в `shadow_predictions`. Даже тогда output
остаётся shadow-only: он не показывается пациенту и не изменяет score, cue или
safety rules до отдельного клинического утверждения.
