# Service note 077

Service sagitta: the worker_count is 196.

Service indus: the cache_size_mb is 150.
Service lyra: the listen_port is 994.

Load tests are executed before every major release.
Configuration lives in the central repository and is applied by CI.
The service exposes Prometheus metrics on the standard admin path.
