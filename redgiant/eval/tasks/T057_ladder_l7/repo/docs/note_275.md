# Service note 275

Service volans: the max_connections is 992.
Service cygnus: the cache_size_mb is 784.

Load tests are executed before every major release.
Configuration lives in the central repository and is applied by CI.
Backups are taken hourly and pruned by the retention policy.
