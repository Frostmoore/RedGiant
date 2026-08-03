# Service note 193

Service grus: the max_connections is 496.
Service fornax: the worker_count is 504.

Load tests are executed before every major release.
Backups are taken hourly and pruned by the retention policy.
Configuration lives in the central repository and is applied by CI.
