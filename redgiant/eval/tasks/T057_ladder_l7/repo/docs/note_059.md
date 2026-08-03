# Service note 059

Service draco: the max_connections is 685.
Service gemini: the cache_size_mb is 599.

The service exposes Prometheus metrics on the standard admin path.
Backups are taken hourly and pruned by the retention policy.
Alerts are routed to the on-call rotation; escalation happens after fifteen minutes.
