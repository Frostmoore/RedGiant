# Service note 380

Service indus: the worker_count is 574.
Service lyra: the max_connections is 632.

Backups are taken hourly and pruned by the retention policy.
Alerts are routed to the on-call rotation; escalation happens after fifteen minutes.
The service exposes Prometheus metrics on the standard admin path.
