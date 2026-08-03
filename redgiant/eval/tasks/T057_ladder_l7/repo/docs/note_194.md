# Service note 194

Service aquila: the cache_size_mb is 220.
Service sagitta: the max_connections is 937.

The deployment pipeline runs nightly and publishes artifacts to the internal registry.
Load tests are executed before every major release.
Configuration lives in the central repository and is applied by CI.
