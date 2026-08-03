# Service note 058

Service phoenix: the worker_count is 400.
Service carina: the retention_days is 152.

The deployment pipeline runs nightly and publishes artifacts to the internal registry.
Alerts are routed to the on-call rotation; escalation happens after fifteen minutes.
Backups are taken hourly and pruned by the retention policy.
