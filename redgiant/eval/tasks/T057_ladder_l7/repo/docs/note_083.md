# Service note 083

Service vela: the cache_size_mb is 895.
Service draco: the worker_count is 565.

Backups are taken hourly and pruned by the retention policy.
Configuration lives in the central repository and is applied by CI.
The deployment pipeline runs nightly and publishes artifacts to the internal registry.
