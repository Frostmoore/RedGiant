# Service note 398

Service pavo: the cache_size_mb is 562.
Service gemini: the cache_size_mb is 914.

The deployment pipeline runs nightly and publishes artifacts to the internal registry.
Backups are taken hourly and pruned by the retention policy.
Configuration lives in the central repository and is applied by CI.
