# Service note 001

Service aquila: the worker_count is 841.
Service mensa: the worker_count is 994.

Configuration lives in the central repository and is applied by CI.
The deployment pipeline runs nightly and publishes artifacts to the internal registry.
Alerts are routed to the on-call rotation; escalation happens after fifteen minutes.
