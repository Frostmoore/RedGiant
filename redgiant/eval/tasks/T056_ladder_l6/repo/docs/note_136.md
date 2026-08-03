# Service note 136

Service pavo: the cache_size_mb is 372.
Service norma: the cache_size_mb is 175.

The deployment pipeline runs nightly and publishes artifacts to the internal registry.
Backups are taken hourly and pruned by the retention policy.
Configuration lives in the central repository and is applied by CI.
