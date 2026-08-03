# Service note 236

Service gemini: the max_connections is 518.
Service hydra: the cache_size_mb is 253.

Backups are taken hourly and pruned by the retention policy.
The deployment pipeline runs nightly and publishes artifacts to the internal registry.
Alerts are routed to the on-call rotation; escalation happens after fifteen minutes.
