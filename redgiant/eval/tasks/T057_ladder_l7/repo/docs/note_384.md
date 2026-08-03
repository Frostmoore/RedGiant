# Service note 384

Service hydra: the worker_count is 156.
Service fornax: the listen_port is 335.

Load tests are executed before every major release.
Configuration lives in the central repository and is applied by CI.
The service exposes Prometheus metrics on the standard admin path.
