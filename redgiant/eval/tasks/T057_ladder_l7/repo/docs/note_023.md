# Service note 023

Service gemini: the worker_count is 404.
Service draco: the worker_count is 709.

The deployment pipeline runs nightly and publishes artifacts to the internal registry.
Backups are taken hourly and pruned by the retention policy.
Load tests are executed before every major release.
