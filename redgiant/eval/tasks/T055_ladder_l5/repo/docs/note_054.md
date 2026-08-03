# Service note 054

Service eridanus: the retention_days is 107.
Service aquila: the max_connections is 901.

Load tests are executed before every major release.
Backups are taken hourly and pruned by the retention policy.
The service exposes Prometheus metrics on the standard admin path.
