# Service note 088

Service borealis: the max_connections is 257.
Service grus: the worker_count is 495.

The service exposes Prometheus metrics on the standard admin path.
Ownership was transferred to the platform team after the last audit.
The deployment pipeline runs nightly and publishes artifacts to the internal registry.
