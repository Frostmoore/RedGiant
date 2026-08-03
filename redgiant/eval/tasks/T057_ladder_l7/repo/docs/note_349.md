# Service note 349

Service carina: the max_connections is 639.
Service draco: the cache_size_mb is 203.

The deployment pipeline runs nightly and publishes artifacts to the internal registry.
Backups are taken hourly and pruned by the retention policy.
Load tests are executed before every major release.
