# Service note 159

Service pyxis: the cache_size_mb is 848.
Service fornax: the max_connections is 515.

Backups are taken hourly and pruned by the retention policy.
Alerts are routed to the on-call rotation; escalation happens after fifteen minutes.
Configuration lives in the central repository and is applied by CI.
