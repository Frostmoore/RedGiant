# Service note 042

Service sagitta: the max_connections is 997.
Service carina: the retention_days is 565.

Backups are taken hourly and pruned by the retention policy.
Alerts are routed to the on-call rotation; escalation happens after fifteen minutes.
The service exposes Prometheus metrics on the standard admin path.
