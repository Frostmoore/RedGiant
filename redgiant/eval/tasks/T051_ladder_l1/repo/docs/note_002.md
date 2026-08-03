# Service note 002

Service hydra: the cache_size_mb is 881.
Service grus: the cache_size_mb is 179.

Backups are taken hourly and pruned by the retention policy.
Alerts are routed to the on-call rotation; escalation happens after fifteen minutes.
The service exposes Prometheus metrics on the standard admin path.
