import fs from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { Presentation, PresentationFile } from '@oai/artifact-tool';

const root = path.resolve(process.argv[2] || process.cwd());
const skill = '/home/muhammad-abyaz/.codex/plugins/cache/openai-primary-runtime/presentations/26.1026.10807/skills/presentations';
const runtimePython = '/home/muhammad-abyaz/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3';
const { finalizePresentation, applyPresentationChartFont } = await import(pathToFileURL(path.join(skill, 'container_tools/artifact_tool_utils.mjs')).href);
process.env.RUNTIME_NODE_MODULES ||= '/home/muhammad-abyaz/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules';
const build = path.join(root, 'results/tmp/slides-build');
const output = path.join(root, 'output/slides');
await fs.mkdir(build, { recursive: true });
await fs.mkdir(output, { recursive: true });
process.chdir(build);
const presentation = Presentation.create({ slideSize: { width: 1280, height: 720 } });
const font = 'DejaVu Sans';
const ink = '#132A42';
const muted = '#52677A';
const teal = '#087F8C';

function text(slide, value, x, y, width, height, size, color = ink, bold = false) {
  const shape = slide.shapes.add({ geometry: 'textbox', position: { left: x, top: y, width, height },
    fill: 'none', line: { fill: 'none', width: 0 } });
  shape.text = value;
  shape.text.style = { typeface: font, fontSize: size, color, bold };
  return shape;
}
function page(title, body, notes, footer = '') {
  const slide = presentation.slides.add();
  slide.background.fill = '#FFFFFF';
  text(slide, title, 72, 54, 1136, 110, 34, ink, true);
  if (body) text(slide, body, 72, 202, 1110, 380, 22);
  if (footer) text(slide, footer, 72, 637, 1136, 40, 19, muted);
  slide.speakerNotes.text = notes;
  return slide;
}
const cover = presentation.slides.add();
cover.background.fill = '#FFFFFF';
text(cover, 'SLO-aware chaos\nengineering', 72, 116, 1120, 205, 43.5, ink, true);
text(cover, 'Cloud-native fault control with separate reliability budgets', 76, 349, 1090, 84, 30, teal);
text(cover, 'Muhammad Awwab Khan and Muhammad Abyaz Khalid\nNED University of Engineering and Technology', 76, 489, 1100, 95, 26, muted);
text(cover, 'Engineering validation and full-study protocol • 3 November 2026'.replace(' • ', ' / '), 76, 635, 1120, 35, 19, muted);
cover.speakerNotes.text = 'Course CEP. Full comparative outcomes remain pending. Source: cas-dc-template.tex and docs/CEP-PLAN.md.';
page('Research questions',
  'How does feedback change overshoot and useful fault exposure?\n\nCan control traffic improve loss estimates under known organic errors?\n\nWhen do telemetry and cleanup reserves make an allocation infeasible?',
  'Primary source: docs/CEP-PLAN.md, RQ1–RQ4. Netflix ChAP already uses control/treatment chaos experiments: https://arxiv.org/abs/1905.04648. Budget-aware placement is prior art: https://doi.org/10.1016/j.future.2026.108620. Related technical disclosure: https://patents.google.com/patent/US12511222B1/en.',
  'SLO-driven injection has prior art. This study tests a particular accounting/control method.');
page('Two SLOs, two ledgers',
  'Availability: client failures and timeouts.\nLatency: requests above 500 ms, including failures.\n\nAdmission freezes each allocation. A cleanup reserve protects the supported delay envelope.\n\nA request may be bad for both objectives. We never add the budgets together.',
  'Source: src/cc_cep/core.py; experiments/PROTOCOL.md. Targets are laboratory choices: 99% availability and 95% within 500 ms. A reservation horizon is not observed long-window SLO validation.');
const correction = page('Zero errors now consume zero budget', '',
  'Eight synthetic healthy intervals of 200 requests each. Old value: 8 * 200 * 1.96^2 / (200 + 1.96^2) = 30.15 requests, from the legacy Wilson interval helper. Revised count-based debit is 0. The real no-fault cluster control separately recorded 2,006 healthy post-baseline treatment outcomes and zero debit. Sources: tests/test_core.py; results/raw/revision-no-fault-01/summary.json.',
  'Synthetic eight-interval replay. Confidence widths are no longer charged as realized events.');
const chart = correction.charts.add('bar', {
  position: { left: 84, top: 205, width: 1100, height: 365 },
  categories: ['Old interval sum', 'Revised debit'],
  series: [{ name: 'Debited requests', values: [30.15, 0], fill: teal }],
  hasLegend: false,
  dataLabels: { showValue: true, position: 'outEnd', textStyle: { fontSize: 25, fill: ink } },
  xAxis: { textStyle: { fontSize: 24, fill: ink } },
  yAxis: { textStyle: { fontSize: 22, fill: muted }, majorGridlines: { fill: '#D9E2E8', width: 1 } },
});
applyPresentationChartFont(chart, { fontFamily: font });
page('Safety and recovery',
  'Faults target the treatment dependency in a disposable namespace.\n\nAn independent watchdog removes expired faults. The heartbeat uses a separate resource.\n\nCleanup requires readback. Exhausted cleanup remains a failed trial after later recovery.',
  'Sources: src/cc_cep/istio.py; src/cc_cep/watchdog.py; tests/test_core.py. The previous controller-crash check removed a fault approximately 7 seconds after SIGKILL. Revised isolation/expiry checks passed. Kubernetes API availability is a required operating assumption.',
  'Operational checks establish tested behavior, not an unconditional safety guarantee.');
page('Full-duration cluster study',
  '80 comparisons: four policies, two faults, two loads, five blocks.\n10 no-fault controls and 20 background attribution ablations.\n\nEach run: 120 s warmup, 300 s fault window, at least 120 s recovery.\n\nPilot costs and policy order freeze before evaluation blocks.',
  'Sources: src/cc_cep/study.py and experiments/FULL-STUDY.md. Main study requires about 14 hours; background ablations add roughly 3 hours. Workload identifiers do not seed Istio fault RNG. Candidate calibrated loads: 48 and 112 requests/s per cohort.',
  'This slide describes the protocol. It does not report completed comparative results.');
page('Attribution has explicit assumptions',
  'Default enforcement charges observed treatment bad events.\n\nBackground credit requires a declared independent, stationary Bernoulli model. A confidence sequence and count bound limit that credit.\n\nShared failures, drift and contamination invalidate this interpretation.',
  'Sources: src/cc_cep/uncertainty.py; docs/ACCOUNTING-V2.md. Established confidence-sequence reference: Howard et al., 2021, https://doi.org/10.1214/20-AOS1991. Model validation is not field causal validation.',
  'Signed estimates remain visible. The enforcement ledger is capped by observed losses.');
page('Evidence and remaining conclusions',
  'Each revised trial retains raw client outcomes, observation snapshots, configuration, source and checksums.\n\nReplay reconciles ledgers against raw counts. Paired intervals resample independent replication blocks.\n\nThe paper includes methodology, validation, threats and a conclusion. Comparative findings remain pending.',
  'Sources: src/cc_cep/replay.py; src/cc_cep/statistics.py; scripts/reproduce_evidence.py. Original development archive is included under results/evidence and has 169 verified checksum manifests. Five replication blocks provide limited precision.',
  'External validity, confirmed novelty and final comparative conclusions require further review.');

for (const [index, slide] of presentation.slides.items.entries()) {
  const png = await presentation.export({ slide, format: 'png', scale: 1 });
  await fs.writeFile(path.join(build, `slide-${index + 1}.png`), new Uint8Array(await png.arrayBuffer()));
}
const candidate = path.join(build, 'candidate.pptx');
await (await PresentationFile.exportPptx(presentation)).save(candidate);
const result = await finalizePresentation({
  workspaceDir: root, candidatePath: candidate,
  finalPath: path.join(output, 'cep-validation-interim-v2.pptx'),
  pythonExecutable: runtimePython,
  integrityValidatorPath: path.join(skill, 'container_tools/inspect_presentation_package_integrity.py'),
  layoutValidatorPath: path.join(skill, 'container_tools/inspect_presentation_layout_geometry.py'),
  layoutArgs: ['--expected-slide-size-emu', '12192000,6858000', '--validate-bullet-geometry', '--validate-heading-fit'],
  explicitTotalSlideCount: 8, requiredNativeChartOwnerSlides: [4], requiredNativeTableOwnerSlides: [],
  fontPolicy: { basis: 'design', families: [font] },
  materializeLiteralChartWorkbooks: true, verifyArtifactToolImport: true,
  receiptPath: path.join(build, 'validation-v2.json'),
});
console.log(JSON.stringify(result));
