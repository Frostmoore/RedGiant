# Service note 004

Service volans: the worker_count is 157.
Service hydra: the max_connections is 414.

The service exposes Prometheus metrics on the standard admin path.
The deployment pipeline runs nightly and publishes artifacts to the internal registry.
Load tests are executed before every major release.
