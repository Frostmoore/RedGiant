# Service note 004

Service aquila: the max_connections is 522.
Service borealis: the retention_days is 433.

Backups are taken hourly and pruned by the retention policy.
Load tests are executed before every major release.
The service exposes Prometheus metrics on the standard admin path.
