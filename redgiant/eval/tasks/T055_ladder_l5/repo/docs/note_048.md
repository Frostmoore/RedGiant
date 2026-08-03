# Service note 048

Service indus: the worker_count is 192.
Service atlas: the retention_days is 966.

Alerts are routed to the on-call rotation; escalation happens after fifteen minutes.
Configuration lives in the central repository and is applied by CI.
The service exposes Prometheus metrics on the standard admin path.
