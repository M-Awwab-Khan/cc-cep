import fs from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { Presentation, PresentationFile } from '@oai/artifact-tool';

const root = path.resolve(process.argv[2] || process.cwd());
const skill = '/home/muhammad-abyaz/.codex/plugins/cache/openai-primary-runtime/presentations/26.1026.10807/skills/presentations';
const runtime = '/home/muhammad-abyaz/.cache/codex-runtimes/codex-primary-runtime/dependencies';
const { finalizePresentation, applyPresentationChartFont } = await import(pathToFileURL(path.join(skill, 'container_tools/artifact_tool_utils.mjs')).href);
process.env.RUNTIME_NODE_MODULES ||= path.join(runtime, 'node/node_modules');
const build = path.join(root, 'results/tmp/final-slides-build');
await fs.mkdir(build, { recursive: true });
const data = JSON.parse(await fs.readFile(path.join(root, 'results/curated/final-study-summary.json'), 'utf8'));
const presentation = Presentation.create({ slideSize: { width: 1280, height: 720 } });
const font = 'DejaVu Sans', ink = '#132A42', teal = '#087F8C', muted = '#52677A';
function text(slide, value, x, y, width, height, size, color=ink, bold=false) {
  const shape = slide.shapes.add({ geometry: 'textbox', position: { left:x, top:y, width, height }, fill:'none', line:{fill:'none',width:0} });
  shape.text = value; shape.text.style = { typeface:font, fontSize:size, color, bold }; return shape;
}
function page(title, body='', notes='', footer='') {
  const s=presentation.slides.add(); s.background.fill='#FFFFFF';
  text(s,title,72,52,1136,110,36,ink,true);
  if(body)text(s,body,72,194,1110,405,25);
  if(footer)text(s,footer,72,634,1136,52,19,muted);
  s.speakerNotes.text=notes; return s;
}
function chart(s,categories,series) {
  const c=s.charts.add('bar',{
    position:{left:80,top:193,width:1110,height:385},categories,series,
    hasLegend:series.length>1,
    legend:{position:'bottom',overlay:false,textStyle:{fontSize:21,fill:ink}},
    dataLabels:{showValue:true,position:'outEnd',textStyle:{fontSize:20,fill:ink}},
    xAxis:{textStyle:{fontSize:22,fill:ink}},
    yAxis:{textStyle:{fontSize:20,fill:muted},majorGridlines:{fill:'#D9E2E8',width:1}},
  }); applyPresentationChartFont(c,{fontFamily:font}); return c;
}
const cover=presentation.slides.add();cover.background.fill='#FFFFFF';
text(cover,'SLO-aware chaos\nengineering',72,109,1120,210,46,ink,true);
text(cover,'A 110-run study of budget control and fault exposure',76,350,1100,85,30,teal);
text(cover,'Muhammad Awwab Khan and Muhammad Abyaz Khalid\nNED University of Engineering and Technology',76,491,1100,90,25,muted);
text(cover,'Cloud Computing CEP / 9 November 2026',76,635,1100,35,20,muted);
cover.speakerNotes.text='Completed full-study-v7. Sources: cas-dc-template.tex; results/raw/full-study-v7/statistical-summary.json. Course study, not a claim of publication acceptance.';
page('Research questions',
 'How does feedback change usable-budget overshoot and fault exposure?\n\nCan matched control traffic improve loss estimates under known background errors?\n\nWhich assumptions limit safety and causal interpretation?',
 'Sources: docs/CEP-PLAN.md; docs/NOVELTY.md. ChAP: https://arxiv.org/html/1905.04648v1. SLO-driven injection prior art: https://patents.google.com/patent/US12511222B1/en.',
 'The research tests a specific implementation and its measured trade-offs.');
page('Architecture and independent budgets',
 'k6 sends matched traffic to separate control and treatment stacks.\nIstio injects 600 ms delays or HTTP 503 aborts into treatment.\n\nAvailability target: 99%. Latency target: 95% within 500 ms.\nA failed request can debit both ledgers.\n\nFeedback changes fault percentage. A separate watchdog removes expired faults.',
 'Sources: deploy/benchmark.yaml; src/cc_cep/istio.py; src/cc_cep/core.py. Frontend/dependency pairs share the same physical node and host transport. Availability and latency counts are never added together.',
 'Core enforcement charges total observed losses. Background credit is a separate ablation.');
const zero=page('Zero observed losses produce zero debit','',
 'Synthetic reproduction of original defect: eight intervals with 200 healthy requests each, 30.15 debited requests from summed Wilson margins. Corrected debit zero. Independently, all ten selected full-study-v7 controls have zero bad requests and zero enforced debit for both SLOs. Sources: tests/test_core.py; results/raw/full-study-v7/outcomes.csv.',
 'Synthetic defect replay shown above. All 10 real no-fault controls also recorded zero debit.');
chart(zero,['Old interval sum','Corrected debit'],[{name:'Debited requests',values:[30.15,0],fill:teal}]);
page('Completed experimental design',
 '80 core comparisons: four policies, two faults, two loads, five blocks.\n10 no-fault controls and 20 background-error ablations.\n\nEach run: 120 s warmup, 300 s fault opportunity, 120 s recovery.\nLoads: 32 and 64 requests/s per cohort after four qualifications.\n\nPolicy order, source, pilot costs and settings froze before comparison.',
 'Sources: experiments/FULL-STUDY.md; results/raw/full-study-v7/plan.json; qualification-plan.json. All 110 selected runs verified and replayed. Five blocks, not 110 replications per contrast. Earlier 48/112 RPS runs are archived and excluded. Istio RNG is not seeded by block identifiers.',
 'Policies: static, threshold stop, calibrated open-loop and adaptive closed-loop.');
const categories=['Abort 32','Abort 64','Delay 32','Delay 64'];
function values(policy,metric){return [['abort',32],['abort',64],['delay',32],['delay',64]].map(([family,rps])=>Number(data.core_latency_slo_means.find(x=>x.family===family&&x.rps===rps&&x.policy===policy)[metric].toFixed(2)));}
const guard=page('Usable-budget overshoot','',
 'Means of five blocks, latency SLO. Abort counts also apply to availability. Data: results/raw/full-study-v7/outcomes.csv; paired-comparisons.csv. Static vs closed-loop differences have descriptive paired 95% intervals excluding zero in each displayed condition. Full-allocation overshoot was zero in every selected run. Reserve 675/1350; usable allocation 480/960 requests.',
 'Mean requests above the usable guard. Full-allocation overshoot was zero for all selected runs.');
chart(guard,categories,[{name:'Static',values:values('static','guard_overshoot'),fill:'#C86B35'},{name:'Adaptive',values:values('closed-loop','guard_overshoot'),fill:teal}]);
const exposure=page('Fault exposure depends on the fault family','',
 'Means of five blocks. Unit: fraction-seconds of API-acknowledged commanded fault percentage. Adaptive minus open-loop: abort32 -8.95 [-9.22,-8.61]; abort64 -9.19 [-9.46,-8.98]; delay32 +0.82 [0.42,1.21]; delay64 +0.80 [0.19,1.20]. Data: paired-comparisons.csv. Intervals descriptive, bootstrap10000, no multiplicity adjustment. This does not measure Envoy application latency.',
 'Mean commanded exposure in fraction-seconds. Adaptive control loses substantial abort exposure.');
chart(exposure,categories,[{name:'Open-loop',values:values('open-loop','exposure'),fill:'#667D91'},{name:'Adaptive',values:values('closed-loop','exposure'),fill:teal}]);
page('Background errors and attribution',
 'Synthetic organic failure probability: 0.5%, independently sampled.\n\nMatched point estimates reduce absolute loss-estimation error by\n66.78 requests at 32 RPS and 134.60 at 64 RPS.\n\nConservative enforcement credit remains zero at 32 RPS.\nAttributed-minus-total exposure intervals include zero at both loads.',
 'Data: background-comparisons.csv; outcomes.csv. Error contrasts on attributed trials: -66.777 [-68.383,-64.971], -134.596 [-138.203,-130.990]. Exposure differences: -0.167 [-0.546,0.090], -0.131 [-0.360,0.098]. Credit mean64 25.911 requests. Synthetic residual reference subtracts tagged organic failures; it is not arbitrary real-world causal ground truth.',
 'Improved point estimates did not establish an exposure benefit from conservative credit.');
page('Safety and the interrupted attempt',
 'Fresh telemetry, minimum traffic, finite fault leases and allocation guards apply to every policy.\n\nOne host sleep interrupted an attempt. The watchdog removed the fault, cleanup verified, and the attempt remained failed.\n\nIts one permitted retry completed. All 111 attempts remain available.',
 'Sources: attempts.csv; results/curated/suspend-incident-2026-11-08.json; failed attempt events/watchdog.log. Host suspend22:23:10 to22:32:21PKT on8Nov. Failure finalized after k6 drain timeout. Both failed and successful attempts verify cleanup. API outages and host shutdown prevent unconditional safety guarantees.',
 'The current dataset has 110 selected runs and one retained invalid attempt.');
page('Reproducibility and statistical limits',
 'Raw outcomes, configurations, frozen source and checksums support ledger replay.\n\nAll 110 selected runs verified. All 96 core paired metric comparisons completed.\n95% bootstrap intervals use five run blocks and 10,000 resamples.\n\nThe single node, shared transport and synthetic backgrounds limit generalization.',
 'Sources: statistical-summary.json; scripts/reproduce_evidence.py; results/evidence/full-study-v7/index.json. Sixteen background contrasts are additional to the96 core contrasts. No multiplicity adjustment. A valid negative result was never retried. Separate archive extraction/replay checks portability.',
 'Five sequential blocks provide limited precision. Intervals are descriptive.');
page('Research findings',
 'Adaptive control reduces guard overshoot relative to static injection.\n\nCalibrated open-loop control remains competitive and delivers more abort exposure.\n\nMatched estimates help under the declared synthetic background model. Conservative credit shows no clear exposure gain.',
 'Sources: final-study-summary.json; cas-dc-template.tex section5. SLO-driven intensity has close prior art in Bertsch US12511222B1. This is an empirical course contribution, not proof of first-ever novelty or production superiority.',
 'The findings support a workload-dependent trade-off, not uniform controller superiority.');
page('Demonstration and next experiments',
 'The recorded trace replays a verified adaptive delay run.\nObserve the latency ledger, intensity changes and cleanup.\n\nNext experiments: correlated backgrounds, independent clusters,\nricher services and infrastructure faults.\n\nA fresh evaluation is required before claiming a retuned controller is better.',
 'Demo source: core-delay-64-closed-loop-1001/attempt-0. The video is recorded data, not a live cluster capture. Online Boutique and Chaos Mesh are optional future extensions. No results are invented for them.',
 'Demo and portable evidence accompany the report.');

for(const [index,slide] of presentation.slides.items.entries()){
 const png=await presentation.export({slide,format:'png',scale:1});
 await fs.writeFile(path.join(build,`slide-${index+1}.png`),new Uint8Array(await png.arrayBuffer()));
}
const candidate=path.join(build,'candidate.pptx');
await(await PresentationFile.exportPptx(presentation)).save(candidate);
const result=await finalizePresentation({workspaceDir:root,candidatePath:candidate,
 finalPath:path.join(root,'output/slides/cep-research-final-v2.pptx'),
 pythonExecutable:path.join(runtime,'python/bin/python3'),
 integrityValidatorPath:path.join(skill,'container_tools/inspect_presentation_package_integrity.py'),
 layoutValidatorPath:path.join(skill,'container_tools/inspect_presentation_layout_geometry.py'),
 layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-bullet-geometry','--validate-heading-fit'],
 explicitTotalSlideCount:12,requiredNativeChartOwnerSlides:[4,6,7],requiredNativeTableOwnerSlides:[],
 fontPolicy:{basis:'design',families:[font]},materializeLiteralChartWorkbooks:true,
 verifyArtifactToolImport:true,receiptPath:path.join(build,'validation-v2.json')});
console.log(JSON.stringify(result));
