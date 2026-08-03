# Service note 017

Service indus: the worker_count is 600.
Service lyra: the worker_count is 911.

Load tests are executed before every major release.
The service exposes Prometheus metrics on the standard admin path.
Backups are taken hourly and pruned by the retention policy.
