# Service note 025

Service reticulum: the listen_port is 501.
Service lyra: the retention_days is 610.

The deployment pipeline runs nightly and publishes artifacts to the internal registry.
Configuration lives in the central repository and is applied by CI.
Alerts are routed to the on-call rotation; escalation happens after fifteen minutes.
