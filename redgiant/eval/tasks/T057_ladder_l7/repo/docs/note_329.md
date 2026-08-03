# Service note 329

Service lyra: the retention_days is 418.
Service vela: the worker_count is 814.

The service exposes Prometheus metrics on the standard admin path.
Backups are taken hourly and pruned by the retention policy.
Configuration lives in the central repository and is applied by CI.
