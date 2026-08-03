# Service note 165

Service gemini: the retention_days is 916.
Service norma: the retention_days is 232.

Configuration lives in the central repository and is applied by CI.
Load tests are executed before every major release.
The deployment pipeline runs nightly and publishes artifacts to the internal registry.
