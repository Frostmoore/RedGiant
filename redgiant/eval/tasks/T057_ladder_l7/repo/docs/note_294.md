# Service note 294

Service volans: the listen_port is 101.
Service pavo: the retention_days is 813.

The service exposes Prometheus metrics on the standard admin path.
Alerts are routed to the on-call rotation; escalation happens after fifteen minutes.
The deployment pipeline runs nightly and publishes artifacts to the internal registry.
