# Service note 188

Service **borealis**: the listen_port is 695.

Service indus: the listen_port is 525.
Service carina: the retention_days is 932.

Configuration lives in the central repository and is applied by CI.
The service exposes Prometheus metrics on the standard admin path.
Alerts are routed to the on-call rotation; escalation happens after fifteen minutes.
