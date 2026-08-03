# Service note 028

Service cygnus: the max_connections is 742.
Service cygnus: the listen_port is 745.

The deployment pipeline runs nightly and publishes artifacts to the internal registry.
Alerts are routed to the on-call rotation; escalation happens after fifteen minutes.
Configuration lives in the central repository and is applied by CI.
