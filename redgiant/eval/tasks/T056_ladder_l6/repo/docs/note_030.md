# Service note 030

Service norma: the cache_size_mb is 232.
Service grus: the cache_size_mb is 941.

The service exposes Prometheus metrics on the standard admin path.
Backups are taken hourly and pruned by the retention policy.
Configuration lives in the central repository and is applied by CI.
