import test from 'node:test';
import assert from 'node:assert/strict';
import {DEFAULT_POLL_MS,MAX_POLL_MS,MIN_POLL_MS,UNKNOWN,diagnosticsRows,formatBytes,formatPercent,
        gpuUnsupported,parseSnapshot,pollIntervalMs,processMemoryBytes,reasonFor,shouldSample}
  from './resourceDiagnostics.ts';

const sampled = {
  version:1, sampled_at:'2026-10-14T00:00:00+00:00', interval_ms:1000,
  cpu_percent_semantics:'100 = one fully busy core; multi-threaded processes may exceed 100',
  process_provider:{provider:'windows_process_counters',status:'ok',reason:null,sampled:2},
  processes:[{role:'app',pid:11,cpu_percent:12.5,rss_bytes:268435456,status:'ok',reasons:{}},
             {role:'agent',pid:12,cpu_percent:null,rss_bytes:null,status:'process_not_found',
              reasons:{rss_bytes:'process_not_found'}}],
  system:{cpu_percent:250.0,cores:8,status:'ok',reasons:{}},
  gpu:{provider:'nvidia-smi',device_name:'NVIDIA GeForce RTX 3070',util_percent:4,
       vram_used_bytes:1073741824,vram_total_bytes:8589934592,status:'ok',reasons:{}},
};
const unsupported = {...sampled, gpu:{provider:null,device_name:null,util_percent:null,
  vram_used_bytes:null,vram_total_bytes:null,status:'unsupported',
  reasons:{device_name:'no_gpu_provider',util_percent:'no_gpu_provider',
           vram_used_bytes:'no_gpu_provider',vram_total_bytes:'no_gpu_provider'}}};

test('a switched-off panel samples nothing and never doubles an in-flight read',()=>{
  assert.equal(shouldSample(false,false),false);
  assert.equal(shouldSample(false,true),false);
  assert.equal(shouldSample(true,true),false);
  assert.equal(shouldSample(true,false),true);
});

test('an unmeasured value is a dash plus the sampler reason, never a zero',()=>{
  assert.equal(formatPercent(null,'provider_missing'),`${UNKNOWN} (provider_missing)`);
  assert.equal(formatBytes(null,'unsupported_platform'),`${UNKNOWN} (unsupported_platform)`);
  assert.equal(formatPercent(null),UNKNOWN);
  assert.ok(!formatPercent(null,'timeout').includes('0'));
  assert.ok(!formatBytes(undefined,'timeout').includes('0'));
  assert.equal(formatPercent(0),'0%');
  assert.equal(formatBytes(0),'0 B');
  assert.equal(reasonFor({status:'unsupported',reasons:{}}, 'cpu_percent'),'unsupported');
  assert.equal(reasonFor(undefined,'cpu_percent'),'no_snapshot');
});

test('bytes scale to binary units and percent keeps the sampler scale',()=>{
  assert.equal(formatBytes(1073741824),'1.0 GiB');
  assert.equal(formatBytes(268435456),'256.0 MiB');
  assert.equal(formatBytes(2048),'2.0 KiB');
  assert.equal(formatBytes(-1),UNKNOWN);
  assert.equal(formatPercent(250),'250%');
});

test('the poll window stays in the low-frequency band',()=>{
  assert.equal(pollIntervalMs(Number.NaN),DEFAULT_POLL_MS);
  assert.equal(pollIntervalMs(undefined),DEFAULT_POLL_MS);
  assert.equal(pollIntervalMs('not a number'),DEFAULT_POLL_MS);
  assert.equal(pollIntervalMs(1),MIN_POLL_MS);
  assert.equal(pollIntervalMs(60000),MAX_POLL_MS);
  assert.equal(pollIntervalMs(2000),2000);
});

test('a reply that is not the sampler contract is refused instead of half-rendered',()=>{
  assert.equal(parseSnapshot(null),null);
  assert.equal(parseSnapshot('{}'),null);
  assert.equal(parseSnapshot([]),null);
  assert.equal(parseSnapshot({}),null);
  assert.equal(parseSnapshot({version:1}),null);
  assert.equal(parseSnapshot({version:1,system:null}),null);
  assert.equal(parseSnapshot({system:{cpu_percent:1}}),null);
  assert.deepEqual(parseSnapshot(sampled),sampled);
});

test('a real snapshot renders the contract fields and labels the memory honestly',()=>{
  const rows=Object.fromEntries(diagnosticsRows(sampled).map(row=>[row.key,row.value]));
  assert.equal(rows.cpu,'250%');
  assert.equal(rows.cores,'8');
  assert.equal(rows.process_memory,'256.0 MiB');
  assert.equal(rows.gpu_device,'NVIDIA GeForce RTX 3070');
  assert.equal(rows.gpu_util,'4%');
  assert.equal(rows.vram_used,'1.0 GiB');
  assert.equal(rows.vram_total,'8.0 GiB');
});

test('memory sums only the rows the sampler could read and counts the rest',()=>{
  assert.deepEqual(processMemoryBytes(sampled.processes),{bytes:268435456,known:1,unknown:1});
  const all=processMemoryBytes([{role:'app',pid:1,rss_bytes:null,reasons:{rss_bytes:'access_denied'}}]);
  assert.equal(all.bytes,null);
  assert.equal(all.unknown,1);
  assert.deepEqual(processMemoryBytes(null),{bytes:null,known:0,unknown:0});
  const rows=diagnosticsRows({version:1,system:{cpu_percent:null,cores:null,status:'unsupported_platform',
    reasons:{cpu_percent:'unsupported_platform',cores:'unsupported_platform'}}});
  assert.equal(rows.find(row=>row.key==='process_memory').value,`${UNKNOWN} (unavailable)`);
});

test('an unsupported GPU provider stays a dash with its reason and no fabricated figure',()=>{
  assert.equal(gpuUnsupported(unsupported),true);
  const rows=Object.fromEntries(diagnosticsRows(unsupported).map(row=>[row.key,row]));
  assert.equal(rows.gpu_util.value,`${UNKNOWN} (no_gpu_provider)`);
  assert.equal(rows.vram_used.value,`${UNKNOWN} (no_gpu_provider)`);
  assert.equal(rows.vram_total.value,`${UNKNOWN} (no_gpu_provider)`);
  assert.equal(rows.gpu_device.reason,'no_gpu_provider');
  assert.equal(gpuUnsupported(sampled),false);
});

test('no row key invites an identifier, a command line or a filesystem path',()=>{
  const banned=['path','user','username','hostname','machine','uuid','serial','command','argv',
                'stdout','stderr','account','domain','executable'];
  for(const row of diagnosticsRows(sampled)){
    assert.ok(!banned.includes(row.key.toLowerCase()),row.key);
  }
  assert.ok(!Object.keys(diagnosticsRows(sampled)).join(',').includes('/'));
});
