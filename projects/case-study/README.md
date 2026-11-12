# DevOps Case Studies

Case studies of real companies from a **DevOps point of view**: what infrastructure, tooling, processes and teams a company needs in order to run every day.

Each case study is based on public information (engineering blogs, annual reports, conference talks). Figures are labelled **Reported** (public) or **Estimated** (illustrative).

| Case study | Industry | Why it's interesting |
|---|---|---|
| [Netflix](netflix-devops.md) | Consumer streaming | Extreme scale, own CDN, chaos engineering, "you build it, you run it" |
| [Monzo](monzo-devops.md) | Regulated digital bank | Cloud-native banking, thousands of microservices, compliance built into the pipeline |
| [Uber](uber-devops.md) | Real-time marketplace | Location-based matching, hybrid multi-cloud, Kafka at huge scale, lessons from security breaches |

## Side-by-Side Comparison

| Area | Netflix | Monzo | Uber |
|---|---|---|---|
| Top priority | Playback always starts | Money is never wrong, payments always work | Every request gets matched in seconds |
| Main health metric | Stream starts per second | Card authorization success rate | Trips requested vs completed, per city |
| Cloud | AWS, 3 regions active-active | AWS London, multi-AZ, plus scheme data centres | Own data centres moving to Oracle Cloud + Google Cloud |
| Compute | EC2 + Titus containers | Kubernetes | Mesos/Peloton, moving to Kubernetes |
| Data | Cassandra, EVCache, S3 + Iceberg | Cassandra, etcd, data warehouse | Schemaless/Docstore (MySQL), Cassandra, Hudi, Pinot |
| Messaging | Kafka + Flink (Keystone) | NSQ, Kafka | Kafka + Flink, Cadence workflows |
| Delivery | Spinnaker + automated canaries | Monorepo + internal deploy tooling | Monorepos, SubmitQueue, Up, per-city flags |
| Resilience method | Chaos engineering, region evacuation | Impact tolerances, game days, reconciliation | Active-active failover, load shedding by priority |
| Biggest external constraint | Studio DRM contracts, ISP partnerships | PRA/FCA regulation, PCI DSS | City-by-city regulation, data residency |

## What Every Company Needs to Run (common to all three)

Use this as a checklist for your own company:

- [ ] **Infrastructure as code**: no manual changes to production
- [ ] **CI/CD with automatic rollback**: small, frequent deploys
- [ ] **One business health metric** watched in real time
- [ ] **Observability**: metrics, logs and traces through a shared library
- [ ] **On-call and incident process**: owners, runbooks, post-mortems
- [ ] **Security in the pipeline**: scans, secrets management, least-privilege access
- [ ] **Redundancy**: at least multi-AZ, with failover that has actually been tested
- [ ] **Graceful degradation**: core features survive when extras fail
- [ ] **Cost visibility** per team or per service
- [ ] **A paved road**: a standard service template and self-service platform

## Template for a New Case Study

Each file follows the same structure:

1. Executive Summary
2. What the Business Needs from Operations
3. Operating Model
4. Layer by layer: Cloud, Compute, Networking, Data, Messaging, Security, Observability, CI/CD, AI/ML, Resilience
5. Summary Table
6. Key Challenges and How They Were Solved
7. Results and Impact (reported vs estimated)
8. Blueprint for a Smaller Company (MVP → Growth → Scale, with monthly cost ranges)
9. Key Takeaways
10. How This Repo Helps (links to the toolkit)
