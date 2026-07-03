# Kenji Morrow — Site Reliability Engineer

## About Me
I'm an SRE at a mid-size fintech company (~300 engineers). I own reliability for our payments infrastructure: uptime targets, incident response, capacity planning, and the oncall rotation. I've been doing this for five years and I have strong opinions about runbooks, postmortems, and what "production ready" actually means. Most outages are caused by humans, not machines.

## How I Work
I run hot during incidents — fast decisions, short messages, actions logged in real time. Outside of incidents I'm methodical: I write things down, I trace causality carefully, I automate things I've had to do twice. I'm oncall one week in four. When I'm not oncall I protect my focus time fiercely.

## My Stack / Tools
- Kubernetes (EKS), Terraform, Helm
- Datadog (metrics + APM + logs), PagerDuty (oncall)
- GitHub Actions for CI/CD pipelines
- Python for automation scripts, Bash for quick ops tasks
- Confluence for runbooks and postmortems

## What I'm Focused On
- Reducing mean time to recovery (MTTR) on payment processing alerts
- Building a better runbook template — ours are inconsistent and incomplete
- Postmortem for last month's 47-minute outage (still overdue)
- Migrating three services to a new cluster with zero-downtime deploys

## How I Want Hermes to Help Me
Help me write runbooks that actually work under pressure: clear decision trees, no ambiguity, escalation paths explicit. Draft postmortem timelines from incident notes. Review Terraform and Kubernetes configs for reliability risks I might have missed. During incidents, help me think through blast radius and rollback options quickly.

## My Definition of "Done Well"
A runbook that an oncall engineer who's never seen the service can follow at 3am. A postmortem that identifies the real contributing factors, not just the proximate cause.
