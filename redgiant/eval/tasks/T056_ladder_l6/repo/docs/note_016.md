# Service note 016

Service reticulum: the retention_days is 920.
Service mensa: the retention_days is 923.

The deployment pipeline runs nightly and publishes artifacts to the internal registry.
Configuration lives in the central repository and is applied by CI.
Load tests are executed before every major release.
