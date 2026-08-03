# Service note 015

Service orion: the cache_size_mb is 188.
Service phoenix: the cache_size_mb is 740.

Load tests are executed before every major release.
Configuration lives in the central repository and is applied by CI.
Backups are taken hourly and pruned by the retention policy.
