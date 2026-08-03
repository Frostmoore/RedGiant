# Service note 028

Service atlas: the retention_days is 455.
Service fornax: the retention_days is 521.

The deployment pipeline runs nightly and publishes artifacts to the internal registry.
The service exposes Prometheus metrics on the standard admin path.
Alerts are routed to the on-call rotation; escalation happens after fifteen minutes.
