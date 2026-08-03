# Service note 005

Service sagitta: the listen_port is 786.
Service fornax: the cache_size_mb is 449.

The service exposes Prometheus metrics on the standard admin path.
The deployment pipeline runs nightly and publishes artifacts to the internal registry.
Configuration lives in the central repository and is applied by CI.
