# Service note 186

Service vela: the max_connections is 539.
Service cygnus: the max_connections is 627.

Configuration lives in the central repository and is applied by CI.
Load tests are executed before every major release.
Alerts are routed to the on-call rotation; escalation happens after fifteen minutes.
