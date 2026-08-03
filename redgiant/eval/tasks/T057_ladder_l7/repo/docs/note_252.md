# Service note 252

Service eridanus: the max_connections is 861.
Service draco: the worker_count is 909.

Configuration lives in the central repository and is applied by CI.
Backups are taken hourly and pruned by the retention policy.
Load tests are executed before every major release.
