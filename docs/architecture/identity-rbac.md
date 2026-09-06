# Identity, RBAC и audit trail

## Tenant context

После `POST /api/v1/auth/login` API выдаёт подписанный короткоживущий token с
`user_id` и активной `organization_id`. На каждом защищённом запросе API
повторно читает действующий membership и role из PostgreSQL. Поэтому удалённый
или отключённый membership немедленно лишает ранее выданный token доступа.

## Роли

Поддерживаются роли из MVP: `patient`, `clinician`, `rehabilitologist`,
`organization_admin`, `research_viewer` и `technical_admin`.

В текущем stage-4 API реализованы следующие границы:

- only `organization_admin` и `technical_admin` создают invitations;
- clinician/rehabilitologist/organization_admin/technical_admin видят
  пациента только в active organization;
- patient получает собственную запись, сопоставленную по `patients.user_id`;
- несовпадающий tenant или недопустимая patient-record связь возвращают `404`,
  без раскрытия существования записи.

Более специализированные permissions (назначения, exports, alerts) будут
реализовываться вместе с соответствующими endpoint на следующих этапах.

## Приглашения

`POST /api/v1/invitations` создаёт ограниченный по времени одноразовый token.
Token возвращается только для local development-потока; production delivery
должен идти через одобренный внеполосный канал. `POST
/api/v1/invitations/accept` создаёт или активирует пользователя и membership.

Безопасное восстановление доступа в текущем MVP выполняется через повторное
ограниченное по времени invitation от organization/technical admin к уже
существующему email: при accept обновляется password и восстанавливается
membership. Самостоятельное восстановление через email/внешний identity provider
пока не реализовано; его нельзя добавлять без утверждённого delivery channel.

Этот путь строго ограничен одним тенантом. Если пользователь с таким email
уже существует и **не** состоит в организации приглашающего админа, и
`POST /api/v1/invitations` (на создании), и `POST /api/v1/invitations/accept`
(перед перезаписью `password_hash`) возвращают `409`. Так invitation не может
быть использован для сброса пароля чужому пользователю, чьи membership
находятся в других организациях.

## Audit

Каждое действие пишет свою `audit_events` строку **в той же транзакции**, что и
само действие (общий cursor, без отдельного соединения), поэтому запись в
журнал не может потеряться независимо от результата.

Логируются: login, создание и принятие invitation, создание версии протокола,
symptom-check и alert-действия; из чтений — просмотр пациента, текущего
протокола и его истории, signal quality и списка alert'ов. Таблица
`audit_events` tenant-scoped; новые клинически значимые действия должны
записываться тем же append-only способом на транзакции запроса.