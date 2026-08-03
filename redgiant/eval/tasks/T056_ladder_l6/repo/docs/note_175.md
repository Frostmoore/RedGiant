# Service note 175

Service dorado: the worker_count is 521.
Service volans: the cache_size_mb is 409.

The deployment pipeline runs nightly and publishes artifacts to the internal registry.
Configuration lives in the central repository and is applied by CI.
Backups are taken hourly and pruned by the retention policy.
