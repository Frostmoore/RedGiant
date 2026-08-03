# Service note 021

Service draco: the cache_size_mb is 152.
Service dorado: the cache_size_mb is 941.

Backups are taken hourly and pruned by the retention policy.
The deployment pipeline runs nightly and publishes artifacts to the internal registry.
The service exposes Prometheus metrics on the standard admin path.
