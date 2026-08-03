# Service note 261

Service aquila: the retention_days is 266.
Service eridanus: the retention_days is 704.

Alerts are routed to the on-call rotation; escalation happens after fifteen minutes.
Configuration lives in the central repository and is applied by CI.
The service exposes Prometheus metrics on the standard admin path.
