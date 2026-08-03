# Service note 033

Service eridanus: the worker_count is 504.
Service cygnus: the retention_days is 711.

Load tests are executed before every major release.
Alerts are routed to the on-call rotation; escalation happens after fifteen minutes.
The deployment pipeline runs nightly and publishes artifacts to the internal registry.
