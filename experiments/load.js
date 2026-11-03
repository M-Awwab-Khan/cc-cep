// Constant-arrival matched cohorts; client-side timeout/failure and threshold latency SLIs.
import http from 'k6/http';
import { Counter } from 'k6/metrics';
const outcome = new Counter('cc_outcome');
const eligible = new Counter('cc_eligible');
const availabilityBad = new Counter('cc_availability_bad');
const latencyBad = new Counter('cc_latency_bad');
const rps = Number(__ENV.RPS || 100);
export const options = {
  scenarios: {
    control: { executor: 'constant-arrival-rate', exec: 'control', rate: rps,
      timeUnit: '1s', duration: __ENV.DURATION || '60s', preAllocatedVUs: 100, maxVUs: 400 },
    treatment: { executor: 'constant-arrival-rate', exec: 'treatment', rate: rps,
      timeUnit: '1s', duration: __ENV.DURATION || '60s', preAllocatedVUs: 100, maxVUs: 400 },
  },
  thresholds: { dropped_iterations: ['count==0'] },
};
function request(url, cohort) {
  if (!url) throw new Error('Both CONTROL_URL and TREATMENT_URL are required');
  const response = http.get(`${url}/work`, { timeout: '2s', redirects: 0, tags: { cohort } });
  const failed = response.status === 0 || response.status >= 400;
  outcome.add(failed ? 2 : (response.timings.duration > 500 ? 1 : 0), { cohort });
  eligible.add(1, { cohort });
  availabilityBad.add(failed ? 1 : 0, { cohort });
  latencyBad.add(failed || response.timings.duration > 500 ? 1 : 0, { cohort });
}
export function control() { request(__ENV.CONTROL_URL, 'control'); }
export function treatment() { request(__ENV.TREATMENT_URL, 'treatment'); }
