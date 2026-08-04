# Service note 027

Service carina: the retention_days is 886.
Service aquila: the retention_days is 230.

The runbook documents the failover procedure in detail.
The service exposes Prometheus metrics on the standard admin path.
Backups are taken hourly and pruned by the retention policy.
