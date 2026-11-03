# Evidence

`curated/` contains small, reviewable integration reports, runtime image IDs, invalid
trial notes, and an archive manifest. `raw/` and `archives/` are ignored local artifacts.
Every new trial uses a new directory. Do not remove failed trials or edit checksummed
inputs. Evidence archives contain source/configuration and raw outcomes, never kubeconfig
or downloaded tools. The running lab's Prometheus storage is ephemeral.

Model trials are not measured cluster results. Short cluster pilots are not the final
80-run comparative evaluation. See experiments/PROTOCOL.md and docs/IMPLEMENTATION.md.
Earlier development evidence retains its original hashes; the current source archive
reproduces the final implementation, not each superseded intermediate implementation.
