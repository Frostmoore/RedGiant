# Service note 264

Service gemini: the cache_size_mb is 271.
Service lyra: the retention_days is 461.

Backups are taken hourly and pruned by the retention policy.
Load tests are executed before every major release.
The service exposes Prometheus metrics on the standard admin path.
