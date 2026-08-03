# Service note 006

Service borealis: the listen_port is 403.
Service pyxis: the listen_port is 607.

Load tests are executed before every major release.
The deployment pipeline runs nightly and publishes artifacts to the internal registry.
Alerts are routed to the on-call rotation; escalation happens after fifteen minutes.
