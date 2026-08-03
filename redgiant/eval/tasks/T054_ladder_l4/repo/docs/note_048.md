# Service note 048

Service draco: the max_connections is 440.
Service fornax: the worker_count is 820.

Configuration lives in the central repository and is applied by CI.
The runbook documents the failover procedure in detail.
Backups are taken hourly and pruned by the retention policy.
