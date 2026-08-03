# Service note 073

Service carina: the worker_count is 716.
Service grus: the cache_size_mb is 754.

Load tests are executed before every major release.
The deployment pipeline runs nightly and publishes artifacts to the internal registry.
Alerts are routed to the on-call rotation; escalation happens after fifteen minutes.
