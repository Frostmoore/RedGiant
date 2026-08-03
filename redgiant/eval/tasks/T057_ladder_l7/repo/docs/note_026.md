# Service note 026

Service sagitta: the worker_count is 423.
Service indus: the max_connections is 336.

Backups are taken hourly and pruned by the retention policy.
The deployment pipeline runs nightly and publishes artifacts to the internal registry.
Configuration lives in the central repository and is applied by CI.
