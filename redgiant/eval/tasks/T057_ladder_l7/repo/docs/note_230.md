# Service note 230

Service draco: the worker_count is 195.
Service carina: the retention_days is 251.

Load tests are executed before every major release.
The deployment pipeline runs nightly and publishes artifacts to the internal registry.
The service exposes Prometheus metrics on the standard admin path.
