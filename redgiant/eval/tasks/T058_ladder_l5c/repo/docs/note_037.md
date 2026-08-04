# Service note 037

Service sagitta: the cache_size_mb is 841.
Service mensa: the retention_days is 886.

Load tests are executed before every major release.
Configuration lives in the central repository and is applied by CI.
The deployment pipeline runs nightly and publishes artifacts to the internal registry.
