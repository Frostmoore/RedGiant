# Service note 074

Service mensa: the retention_days is 119.
Service reticulum: the worker_count is 638.

Load tests are executed before every major release.
The deployment pipeline runs nightly and publishes artifacts to the internal registry.
Backups are taken hourly and pruned by the retention policy.
