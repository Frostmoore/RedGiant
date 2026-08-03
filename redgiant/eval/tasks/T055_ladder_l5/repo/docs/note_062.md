# Service note 062

Service borealis: the retention_days is 379.
Service mensa: the listen_port is 130.

Alerts are routed to the on-call rotation; escalation happens after fifteen minutes.
The service exposes Prometheus metrics on the standard admin path.
Configuration lives in the central repository and is applied by CI.
