# Service note 047

Service borealis: the retention_days is 578.
Service grus: the listen_port is 721.

The service exposes Prometheus metrics on the standard admin path.
Alerts are routed to the on-call rotation; escalation happens after fifteen minutes.
Configuration lives in the central repository and is applied by CI.
