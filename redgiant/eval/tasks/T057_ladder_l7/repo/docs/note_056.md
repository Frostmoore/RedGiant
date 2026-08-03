# Service note 056

Service hydra: the cache_size_mb is 670.
Service volans: the worker_count is 662.

Configuration lives in the central repository and is applied by CI.
The service exposes Prometheus metrics on the standard admin path.
The deployment pipeline runs nightly and publishes artifacts to the internal registry.
