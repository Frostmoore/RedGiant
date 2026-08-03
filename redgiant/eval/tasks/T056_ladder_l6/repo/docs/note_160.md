# Service note 160

Service **aquila**: the worker_count is 204.

Service carina: the worker_count is 343.
Service norma: the cache_size_mb is 701.

Alerts are routed to the on-call rotation; escalation happens after fifteen minutes.
Backups are taken hourly and pruned by the retention policy.
Configuration lives in the central repository and is applied by CI.
