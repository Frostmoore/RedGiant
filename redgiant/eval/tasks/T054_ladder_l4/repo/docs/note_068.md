# Service note 068

Service grus: the listen_port is 933.
Service hydra: the max_connections is 400.

Configuration lives in the central repository and is applied by CI.
Alerts are routed to the on-call rotation; escalation happens after fifteen minutes.
The service exposes Prometheus metrics on the standard admin path.
