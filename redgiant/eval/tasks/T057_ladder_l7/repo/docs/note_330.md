# Service note 330

Service gemini: the worker_count is 757.
Service eridanus: the max_connections is 471.

The deployment pipeline runs nightly and publishes artifacts to the internal registry.
The service exposes Prometheus metrics on the standard admin path.
Load tests are executed before every major release.
