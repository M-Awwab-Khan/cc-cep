# Decisions and assumptions

## Accepted initialization choices
- Preserve the existing manuscript filename to minimize Overleaf main-document disruption.
- Keep the two-column CAS class, original vendor sources, and email icon.
- Use bundled cas-model2-names.bst instead of the absent elsarticle-num-names.bst.
- Initialize Git without making an initial commit or configuring a remote.
- Preserve existing research text and bibliography; indexing, novelty, and verification assertions still require evidence.
- Remove unused template distribution examples and documentation; retain original README and manifest.

## Provisional implementation decisions
- Python controller, Prometheus/Grafana observability, Kubernetes, and k6 load generation.
- Start with a small instrumented microservice application; use Online Boutique for external validity after the core works.
- Request-level Istio delay/abort injection for controllable intensity; Chaos Mesh for later infrastructure fault scenarios.
- Prefer independent, matched experiment/control application stacks for attribution; prove isolation and request labeling in a spike.
- Aim for an eight-week schedule with a four-week minimum-scope fallback.

## Historical initialization inputs (superseded by the implementation decisions below)
Course brief/rubric and required CEP learning outcomes; submission date/page limit; laptop CPU/RAM and Docker/WSL availability; cloud credits/provider and cost ceiling; instructor expectations for novelty, experiments, and permitted references.
At initialization, no deployment or cloud spend had been initiated.


## Implementation decisions — 3 November 2026

- User authorized implementation and installation, supplied a 16 November deadline,
  reported no rubric, and freed RAM for a local cluster. Use the neighboring cc-cep Git
  repository; leave the Terraform lab untouched. No cloud spend.
- Install checksum-verified kind 0.33.0, kubectl 1.36.0, Istioctl 1.31.3, Helm 4.3.1,
  k6 2.3.0 under ignored .tools/bin. Pin package resolution in uv.lock. Use digest-pinned
  Python, kind node, Prometheus and Grafana images. Record actual runtime image IDs.
- Dedicated kind cluster cc-cep, namespace cc-cep, separate control/treatment frontend
  and dependency services. Faults target only the treatment dependency hostname; do not
  depend on downstream propagation of a cohort header. Shared-node interference remains.
- Treat client k6 outcome points as count telemetry, including failed connections and
  timeouts. Server Prometheus histograms support inspection, not latency-budget arithmetic.
- Reserve fixed bad-request allocations. Refuse admission when the declared lag/removal
  reserve cannot fit. Pilot's larger laboratory reservation is explicit in PROTOCOL.md;
  it is not evidence over a real long SLO window.
- Keep signed excess estimates and a clipped Wilson-based enforcement screen separately.
  The screen is not a time-uniform confidence guarantee and creates stopping bias.
- Use monotonic time for durations/exposure and UTC timestamps for evidence. Exposure is
  the API-acknowledged command integral; Envoy propagation introduces measurement error.
- Controller restart never resumes an old fault intensity. Use a target lock, atomic
  checkpoints, cleanup-before-admission, finite leases, and a separate bounded watchdog.
  The lock is host-local; a distributed Kubernetes leader lease remains a future gate.
- First cluster spike exposed a shared-resource optimistic-write race. Keep failed/invalid
  evidence. Move watchdog heartbeat to the safety ConfigMap; it no longer rewrites fault
  routing on each heartbeat. Strengthen expiry checks to reject premature removal.
- Include post-stop client counts in cleanup-tail accounting. Checkpoint state and
  preserve cleanup errors rather than treating a stop command as removal proof.
- Preserve all manuscript text and vendor assets. DOI metadata audit is separate from
  claim verification. No final novelty, statistical advantage, or causal claim yet.

## Interactive learning visualizer

- Added a separate static website under visualizer/ using the Sites plugin. It has its own Sites source repository and hosting identity; it does not modify the CEP controller or deploy cluster resources.
- The browser simulation uses seeded synthetic requests, a fixed 120-second reservation, and up to 60 simulated seconds. Default point-estimate accounting and simplified feedback are teaching choices, not proposed fixes or verified research results.
- An optional Wilson-screen mode reproduces the prototype's per-interval formula to explain zero-error enforcement spending. No causal, safety, or superiority guarantee is implied.
- Includes a live sandbox, independent SLO ledgers, four-policy comparison, glossary, guided explanations, quiz, accessible chart data, and JSON export.
- Verified nine model checks plus Chrome interactions and desktop/mobile layout. Publication defaults to owner-private.
