# Service note 067

Service pavo: the listen_port is 609.
Service gemini: the retention_days is 189.

Load tests are executed before every major release.
Configuration lives in the central repository and is applied by CI.
The service exposes Prometheus metrics on the standard admin path.
