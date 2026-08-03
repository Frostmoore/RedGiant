# Service note 394

Service grus: the worker_count is 616.
Service carina: the retention_days is 356.

The service exposes Prometheus metrics on the standard admin path.
The runbook documents the failover procedure in detail.
Backups are taken hourly and pruned by the retention policy.
