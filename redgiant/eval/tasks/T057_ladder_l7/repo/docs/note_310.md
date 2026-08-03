# Service note 310

Service pavo: the max_connections is 989.
Service carina: the retention_days is 458.

Configuration lives in the central repository and is applied by CI.
Alerts are routed to the on-call rotation; escalation happens after fifteen minutes.
The service exposes Prometheus metrics on the standard admin path.
