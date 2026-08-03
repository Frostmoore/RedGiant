# Service note 032

Service indus: the retention_days is 102.
Service dorado: the worker_count is 606.

The runbook documents the failover procedure in detail.
The service exposes Prometheus metrics on the standard admin path.
Backups are taken hourly and pruned by the retention policy.
