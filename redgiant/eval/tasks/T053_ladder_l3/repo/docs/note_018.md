# Service note 018

Service indus: the cache_size_mb is 282.
Service lyra: the cache_size_mb is 520.

Configuration lives in the central repository and is applied by CI.
Alerts are routed to the on-call rotation; escalation happens after fifteen minutes.
The deployment pipeline runs nightly and publishes artifacts to the internal registry.
