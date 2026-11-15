# Demonstration

The final ten-second MP4 replays recorded observations from the verified adaptive delay
run `core-delay-64-closed-loop-1001/attempt-0`. It represents about 426 seconds after
admission, including recovery. It is explicitly labelled recorded data, not a live
cluster capture. The plots show full allocation, usable guard, debit and requested
intensity. Earlier engineering-pilot videos remain historical.

```sh
uv run python scripts/build_demo.py \
  --run results/raw/full-study-v7/core-delay-64-closed-loop-1001/attempt-0 \
  --output output/demo/cep-study-recorded-trace.mp4
```

Suggested viva sequence (about five minutes):

1. Explain the two request-count SLO ledgers and why failure can debit both.
2. Show the ten no-fault controls: zero bad outcomes and zero debit.
3. Play the trace. Identify the latency debit, changes in intensity and removal before
   recovery. The intensity plot shows the next request, not measured Envoy propagation.
4. Explain the paired results: adaptive guard reduction versus static, less abort exposure
   versus calibrated open-loop, and no clear exposure benefit from background credit.
5. Show the evidence index, failed sleep-interrupted attempt, its successful retry and
   the portable replay command. State the single-node and synthetic-background limits.

This scripted recorded demonstration is ready for student rehearsal. A fresh live demo
requires another scoped safety check and a new output directory; do not overwrite the
study or claim fresh results without recording them. The target lock refuses simultaneous
controllers. Emergency stop: create results/tmp/EMERGENCY_STOP, then verify fault absence.
