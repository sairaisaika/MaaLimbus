/**
 * Presentation logic for the opt-in local resource-diagnostics panel.
 *
 * It is pure so it runs without a window, a device or the game: every field it
 * reads is a field the read-only sampler in `src/maalimbus/resource_diagnostics.py`
 * actually exports. The sampler's own rules are repeated here, never relaxed:
 * a value that is absent is shown as the unknown mark together with the sampler's
 * short machine-readable reason, never as a zero and never as a guess.
 *
 * Nothing in this module reads or writes files, holds the controller lease or
 * sends gameplay input; the panel only ever maps an already-sampled snapshot.
 */

export type Reasons = Record<string, string>;

export type ProcessRow = {
  role?: string | null;
  pid?: number | null;
  cpu_percent?: number | null;
  rss_bytes?: number | null;
  status?: string | null;
  reasons?: Reasons | null;
};

export type SystemBlock = {
  cpu_percent?: number | null;
  cores?: number | null;
  status?: string | null;
  reasons?: Reasons | null;
};

export type GpuBlock = {
  provider?: string | null;
  device_name?: string | null;
  util_percent?: number | null;
  vram_used_bytes?: number | null;
  vram_total_bytes?: number | null;
  status?: string | null;
  reasons?: Reasons | null;
};

export type Snapshot = {
  version?: number;
  sampled_at?: string | null;
  interval_ms?: number | null;
  cpu_percent_semantics?: string | null;
  process_provider?: {provider?: string | null; status?: string | null; reason?: string | null;
                      sampled?: number | null} | null;
  processes?: ProcessRow[] | null;
  system?: SystemBlock | null;
  gpu?: GpuBlock | null;
};

export type Row = {key: string; value: string; reason: string | null};

/** The mark for "not measured": a dash, never 0 and never a stand-in number. */
export const UNKNOWN = '—';
/** The panel samples nothing until the user switches it on; this is its window. */
export const DEFAULT_POLL_MS = 1000;
export const MIN_POLL_MS = 500;
export const MAX_POLL_MS = 15000;

/**
 * The opt-in gate. A disabled panel must not issue a sample at all, and a
 * request already in flight is never doubled up.
 */
export function shouldSample(enabled: boolean, inFlight: boolean): boolean {
  return enabled === true && inFlight !== true;
}

/** Clamp the requested window into the low-frequency band the panel may poll. */
export function pollIntervalMs(value: unknown): number {
  const parsed = typeof value === 'number' ? value : Number(value);
  if (!Number.isFinite(parsed)) return DEFAULT_POLL_MS;
  return Math.min(MAX_POLL_MS, Math.max(MIN_POLL_MS, Math.trunc(parsed)));
}

/**
 * Accept only a reply that carries the sampler's contract version and a system
 * block. Anything else is refused rather than half-rendered.
 */
export function parseSnapshot(value: unknown): Snapshot | null {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) return null;
  const snapshot = value as Snapshot;
  if (typeof snapshot.version !== 'number') return null;
  if (snapshot.system === null || typeof snapshot.system !== 'object') return null;
  return snapshot;
}

/** The reason the sampler gave for one field, falling back to the block's status. */
export function reasonFor(block: {reasons?: Reasons | null; status?: string | null} | null | undefined,
                          key: string): string {
  if (block === null || block === undefined) return 'no_snapshot';
  const reasons = block.reasons || {};
  if (reasons[key]) return reasons[key];
  if (block.status && block.status !== 'ok' && block.status !== 'partial') return block.status;
  return 'unavailable';
}

/** The unknown mark with the sampler's own reason attached when there is one. */
export function unknownMark(reason?: string | null): string {
  return reason ? `${UNKNOWN} (${reason})` : UNKNOWN;
}

export function formatPercent(value: number | null | undefined, reason?: string | null): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) return unknownMark(reason);
  return `${value}%`;
}

export function formatBytes(value: number | null | undefined, reason?: string | null): string {
  if (typeof value !== 'number' || !Number.isFinite(value) || value < 0) return unknownMark(reason);
  const units = ['B', 'KiB', 'MiB', 'GiB', 'TiB'];
  let amount = value, unit = 0;
  while (amount >= 1024 && unit < units.length - 1) {
    amount /= 1024;
    unit += 1;
  }
  return `${unit === 0 ? amount : amount.toFixed(1)} ${units[unit]}`;
}

/**
 * Memory from the only memory figures the sampler exports: the working set
 * (RSS) of each sampled process. There is no machine-wide RAM total in the
 * snapshot, so this is honestly labelled as process memory, and rows the
 * sampler could not read are counted instead of being treated as zero.
 */
export function processMemoryBytes(rows: ProcessRow[] | null | undefined):
    {bytes: number | null; known: number; unknown: number} {
  const list = Array.isArray(rows) ? rows : [];
  let bytes = 0, known = 0, unknown = 0;
  for (const row of list) {
    const value = row ? row.rss_bytes : null;
    if (typeof value === 'number' && Number.isFinite(value) && value >= 0) {
      bytes += value;
      known += 1;
    } else {
      unknown += 1;
    }
  }
  return {bytes: known > 0 ? bytes : null, known, unknown};
}

/**
 * The panel's rows as key/value/reason. Keys are stable so the panel owns the
 * localized labels; the values are already formatted with the unknown rule.
 */
export function diagnosticsRows(snapshot: Snapshot | null): Row[] {
  const system = snapshot ? snapshot.system : null;
  const gpu = snapshot ? snapshot.gpu : null;
  const memory = processMemoryBytes(snapshot ? snapshot.processes : null);
  const memoryReason = memory.unknown > 0 ? 'partial' : 'unavailable';
  const cores = system && typeof system.cores === 'number' ? String(system.cores) : UNKNOWN;
  return [
    {key: 'cpu', value: formatPercent(system?.cpu_percent, reasonFor(system, 'cpu_percent')),
     reason: reasonFor(system, 'cpu_percent')},
    {key: 'cores', value: cores, reason: cores === UNKNOWN ? reasonFor(system, 'cores') : null},
    {key: 'process_memory', value: formatBytes(memory.bytes, memoryReason),
     reason: memory.bytes === null ? memoryReason : (memory.unknown > 0 ? 'partial' : null)},
    {key: 'gpu_device', value: gpu?.device_name || unknownMark(reasonFor(gpu, 'device_name')),
     reason: gpu?.device_name ? null : reasonFor(gpu, 'device_name')},
    {key: 'gpu_util', value: formatPercent(gpu?.util_percent, reasonFor(gpu, 'util_percent')),
     reason: reasonFor(gpu, 'util_percent')},
    {key: 'vram_used', value: formatBytes(gpu?.vram_used_bytes, reasonFor(gpu, 'vram_used_bytes')),
     reason: reasonFor(gpu, 'vram_used_bytes')},
    {key: 'vram_total', value: formatBytes(gpu?.vram_total_bytes, reasonFor(gpu, 'vram_total_bytes')),
     reason: reasonFor(gpu, 'vram_total_bytes')},
  ];
}

/** Per-process rows for the detail table; unknown figures stay dashed. */
export function processRows(snapshot: Snapshot | null): ProcessRow[] {
  return snapshot && Array.isArray(snapshot.processes) ? snapshot.processes : [];
}

/** A short, machine-readable line for the GPU provider state. */
export function gpuStatus(snapshot: Snapshot | null): string {
  const gpu = snapshot ? snapshot.gpu : null;
  if (!gpu) return 'no_gpu_provider';
  return gpu.status || 'unavailable';
}

/** True when every row except the GPU device name came back unsupported. */
export function gpuUnsupported(snapshot: Snapshot | null): boolean {
  const gpu = snapshot ? snapshot.gpu : null;
  return !!gpu && gpu.status === 'unsupported';
}
