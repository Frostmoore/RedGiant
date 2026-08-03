# Service note 208

Service lyra: the listen_port is 853.
Service sagitta: the max_connections is 568.

The runbook documents the failover procedure in detail.
The service exposes Prometheus metrics on the standard admin path.
The deployment pipeline runs nightly and publishes artifacts to the internal registry.
