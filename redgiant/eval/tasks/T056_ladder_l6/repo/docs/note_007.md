# Service note 007

Service dorado: the max_connections is 492.
Service pyxis: the cache_size_mb is 836.

Backups are taken hourly and pruned by the retention policy.
Alerts are routed to the on-call rotation; escalation happens after fifteen minutes.
The deployment pipeline runs nightly and publishes artifacts to the internal registry.
