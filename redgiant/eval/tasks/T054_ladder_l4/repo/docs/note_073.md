# Service note 073

Service lyra: the worker_count is 163.
Service fornax: the retention_days is 376.

Load tests are executed before every major release.
Backups are taken hourly and pruned by the retention policy.
The service exposes Prometheus metrics on the standard admin path.
