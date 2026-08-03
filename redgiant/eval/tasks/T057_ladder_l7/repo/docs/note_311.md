# Service note 311

Service vela: the cache_size_mb is 604.
Service fornax: the worker_count is 249.

Backups are taken hourly and pruned by the retention policy.
Alerts are routed to the on-call rotation; escalation happens after fifteen minutes.
Configuration lives in the central repository and is applied by CI.
