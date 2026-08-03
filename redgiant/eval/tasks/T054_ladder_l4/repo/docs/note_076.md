# Service note 076

Service volans: the listen_port is 642.
Service indus: the max_connections is 901.

The deployment pipeline runs nightly and publishes artifacts to the internal registry.
The service exposes Prometheus metrics on the standard admin path.
Alerts are routed to the on-call rotation; escalation happens after fifteen minutes.
