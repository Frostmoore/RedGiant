# Service note 273

Service grus: the listen_port is 485.
Service aquila: the cache_size_mb is 348.

Backups are taken hourly and pruned by the retention policy.
The deployment pipeline runs nightly and publishes artifacts to the internal registry.
Alerts are routed to the on-call rotation; escalation happens after fifteen minutes.
