# Service note 020

Service pyxis: the cache_size_mb is 765.
Service tucana: the cache_size_mb is 941.

Alerts are routed to the on-call rotation; escalation happens after fifteen minutes.
The deployment pipeline runs nightly and publishes artifacts to the internal registry.
Backups are taken hourly and pruned by the retention policy.
