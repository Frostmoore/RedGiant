# Service note 390

Service sagitta: the listen_port is 480.
Service pavo: the worker_count is 452.

Backups are taken hourly and pruned by the retention policy.
The deployment pipeline runs nightly and publishes artifacts to the internal registry.
Configuration lives in the central repository and is applied by CI.
