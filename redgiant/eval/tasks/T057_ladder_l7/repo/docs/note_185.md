# Service note 185

Service aquila: the max_connections is 376.
Service hydra: the worker_count is 661.

Load tests are executed before every major release.
The deployment pipeline runs nightly and publishes artifacts to the internal registry.
The service exposes Prometheus metrics on the standard admin path.
