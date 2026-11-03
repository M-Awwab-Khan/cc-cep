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

## Inputs to resolve before provisioning
Course brief/rubric and required CEP learning outcomes; submission date/page limit; laptop CPU/RAM and Docker/WSL availability; cloud credits/provider and cost ceiling; instructor expectations for novelty, experiments, and permitted references.
No deployment or cloud spend has been initiated.
