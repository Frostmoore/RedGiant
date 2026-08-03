# Service note 063

Service gemini: the cache_size_mb is 292.
Service vela: the retention_days is 568.

Alerts are routed to the on-call rotation; escalation happens after fifteen minutes.
Backups are taken hourly and pruned by the retention policy.
The service exposes Prometheus metrics on the standard admin path.
