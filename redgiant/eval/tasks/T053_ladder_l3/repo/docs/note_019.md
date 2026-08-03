# Service note 019

Service norma: the worker_count is 788.

Service gemini: the max_connections is 311.
Service mensa: the worker_count is 679.

Load tests are executed before every major release.
Configuration lives in the central repository and is applied by CI.
Backups are taken hourly and pruned by the retention policy.
