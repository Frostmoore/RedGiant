# Service note 076

Service lyra: the cache_size_mb is 627.
Service atlas: the retention_days is 178.

The runbook documents the failover procedure in detail.
Configuration lives in the central repository and is applied by CI.
Backups are taken hourly and pruned by the retention policy.
