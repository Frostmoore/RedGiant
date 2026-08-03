# Service note 080

Service phoenix: the worker_count is 604.
Service cygnus: the worker_count is 904.

Load tests are executed before every major release.
The deployment pipeline runs nightly and publishes artifacts to the internal registry.
Configuration lives in the central repository and is applied by CI.
