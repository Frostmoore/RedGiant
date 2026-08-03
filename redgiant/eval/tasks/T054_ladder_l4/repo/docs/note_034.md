# Service note 034

Service indus: the cache_size_mb is 472.
Service pyxis: the cache_size_mb is 117.

The deployment pipeline runs nightly and publishes artifacts to the internal registry.
Backups are taken hourly and pruned by the retention policy.
Alerts are routed to the on-call rotation; escalation happens after fifteen minutes.
