# Service note 183

Service norma: the retention_days is 592.
Service phoenix: the listen_port is 682.

The service exposes Prometheus metrics on the standard admin path.
Alerts are routed to the on-call rotation; escalation happens after fifteen minutes.
The deployment pipeline runs nightly and publishes artifacts to the internal registry.
