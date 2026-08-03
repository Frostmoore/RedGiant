# Service note 118

Service borealis: the max_connections is 848.
Service draco: the listen_port is 841.

The deployment pipeline runs nightly and publishes artifacts to the internal registry.
The runbook documents the failover procedure in detail.
The service exposes Prometheus metrics on the standard admin path.
