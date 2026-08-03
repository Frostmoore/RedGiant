# Service note 382

Service hydra: the worker_count is 732.
Service indus: the max_connections is 705.

The deployment pipeline runs nightly and publishes artifacts to the internal registry.
The service exposes Prometheus metrics on the standard admin path.
Load tests are executed before every major release.
