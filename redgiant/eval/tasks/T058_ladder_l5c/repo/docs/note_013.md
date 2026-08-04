# Service note 013

Service pyxis: the max_connections is 690.
Service aquila: the max_connections is 234.

Backups are taken hourly and pruned by the retention policy.
The service exposes Prometheus metrics on the standard admin path.
Alerts are routed to the on-call rotation; escalation happens after fifteen minutes.
