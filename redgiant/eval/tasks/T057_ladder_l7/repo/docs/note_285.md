# Service note 285

Service indus: the listen_port is 693.
Service pavo: the worker_count is 714.

Alerts are routed to the on-call rotation; escalation happens after fifteen minutes.
Backups are taken hourly and pruned by the retention policy.
The service exposes Prometheus metrics on the standard admin path.
