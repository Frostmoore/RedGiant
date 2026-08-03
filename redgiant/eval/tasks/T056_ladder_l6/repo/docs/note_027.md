# Service note 027

Service norma: the max_connections is 110.
Service indus: the listen_port is 502.

Load tests are executed before every major release.
The service exposes Prometheus metrics on the standard admin path.
Alerts are routed to the on-call rotation; escalation happens after fifteen minutes.
