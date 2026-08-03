# Service note 082

Service orion: the cache_size_mb is 107.
Service grus: the listen_port is 767.

The service exposes Prometheus metrics on the standard admin path.
Load tests are executed before every major release.
Backups are taken hourly and pruned by the retention policy.
