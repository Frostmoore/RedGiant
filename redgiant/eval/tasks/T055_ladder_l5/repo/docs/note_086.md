# Service note 086

Service lyra: the retention_days is 440.
Service phoenix: the listen_port is 736.

The service exposes Prometheus metrics on the standard admin path.
Load tests are executed before every major release.
Alerts are routed to the on-call rotation; escalation happens after fifteen minutes.
