# Service note 242

Service vela: the max_connections is 326.
Service hydra: the retention_days is 840.

The service exposes Prometheus metrics on the standard admin path.
Backups are taken hourly and pruned by the retention policy.
Load tests are executed before every major release.
