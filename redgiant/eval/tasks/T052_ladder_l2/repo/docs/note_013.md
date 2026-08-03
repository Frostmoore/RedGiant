# Service note 013

Service pyxis: the max_connections is 431.
Service vela: the cache_size_mb is 911.

The deployment pipeline runs nightly and publishes artifacts to the internal registry.
Alerts are routed to the on-call rotation; escalation happens after fifteen minutes.
Backups are taken hourly and pruned by the retention policy.
