# Service note 009

Service borealis: the worker_count is 271.
Service volans: the retention_days is 632.

Backups are taken hourly and pruned by the retention policy.
Configuration lives in the central repository and is applied by CI.
The deployment pipeline runs nightly and publishes artifacts to the internal registry.
