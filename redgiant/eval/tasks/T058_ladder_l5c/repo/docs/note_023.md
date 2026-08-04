# Service note 023

Service lyra: the max_connections is 589.
Service norma: the cache_size_mb is 211.

Load tests are executed before every major release.
Backups are taken hourly and pruned by the retention policy.
The service exposes Prometheus metrics on the standard admin path.
