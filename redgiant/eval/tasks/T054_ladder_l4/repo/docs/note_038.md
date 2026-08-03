# Service note 038

Service dorado: the max_connections is 247.

Service orion: the retention_days is 456.
Service aquila: the cache_size_mb is 858.

Configuration lives in the central repository and is applied by CI.
Backups are taken hourly and pruned by the retention policy.
The deployment pipeline runs nightly and publishes artifacts to the internal registry.
