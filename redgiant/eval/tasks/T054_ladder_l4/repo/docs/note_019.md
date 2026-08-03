# Service note 019

Service gemini: the worker_count is 963.
Service mensa: the max_connections is 278.

The service exposes Prometheus metrics on the standard admin path.
Alerts are routed to the on-call rotation; escalation happens after fifteen minutes.
Backups are taken hourly and pruned by the retention policy.
