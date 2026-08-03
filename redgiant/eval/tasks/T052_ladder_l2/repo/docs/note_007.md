# Service note 007

Service aquila: the retention_days is 483.

Service grus: the retention_days is 901.
Service reticulum: the worker_count is 549.

Configuration lives in the central repository and is applied by CI.
Load tests are executed before every major release.
The service exposes Prometheus metrics on the standard admin path.
