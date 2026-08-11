export type C2paVerdict = 'verified' | 'invalid' | 'inconclusive' | 'not-found'

export interface C2paTimelineEvent {
  action: string
  description: string
  when?: string
}

export interface C2paVerificationResult {
  verdict: C2paVerdict
  hasManifest: boolean
  manifestCount: number
  activeManifest: string
  claimGenerator: string
  sourceType: string
  validationIssues: string[]
  timeline: C2paTimelineEvent[]
  hash: string
}

let c2paPromise: Promise<any> | null = null

async function getC2pa() {
  if (!c2paPromise) {
    c2paPromise = Promise.all([
      import('@contentauth/c2pa-web'),
      import('@contentauth/c2pa-web/resources/c2pa.wasm?url'),
    ]).then(([sdk, wasm]) => sdk.createC2pa({ wasmSrc: wasm.default }))
  }
  return c2paPromise
}

function emptyResult(hash: string): C2paVerificationResult {
  return {
    verdict: 'not-found', hasManifest: false, manifestCount: 0,
    activeManifest: '', claimGenerator: '', sourceType: '',
    validationIssues: [], timeline: [], hash,
  }
}

function issueText(item: unknown): string {
  if (typeof item === 'string') return item
  if (!item || typeof item !== 'object') return String(item)
  const issue = item as Record<string, unknown>
  return String(issue.explanation || issue.code || JSON.stringify(issue))
}

function extractTimeline(assertions: unknown[], claimGenerator: string): C2paTimelineEvent[] {
  const events: C2paTimelineEvent[] = []
  for (const assertion of assertions) {
    if (!assertion || typeof assertion !== 'object') continue
    const record = assertion as Record<string, any>
    const label = String(record.label || record.url || '')
    if (!/actions/i.test(label)) continue
    const data = record.data || record.value || record
    const actions = Array.isArray(data?.actions) ? data.actions : []
    for (const entry of actions) {
      events.push({
        action: String(entry?.action || entry?.type || 'c2pa.edited'),
        description: String(entry?.description || entry?.softwareAgent || entry?.software_agent || entry?.action || '已记录的 C2PA 操作'),
        ...(entry?.when || entry?.timestamp ? { when: String(entry.when || entry.timestamp) } : {}),
      })
    }
  }
  if (!events.length && claimGenerator) {
    events.push({ action: 'c2pa.created', description: claimGenerator })
  }
  return events
}

function findSourceType(assertions: unknown[]): string {
  const match = JSON.stringify(assertions).match(/https?:\\?\/\\?\/cv\.iptc\.org\\?\/newscodes\\?\/digitalsourcetype\\?\/[A-Za-z]+/i)
  return match?.[0]?.replaceAll('\\/', '/').split('/').pop() || ''
}

export function normalizeC2paStore(store: unknown, hash: string): C2paVerificationResult {
  if (!store || typeof store !== 'object') return emptyResult(hash)
  const record = store as Record<string, any>
  const manifests = record.manifests && !Array.isArray(record.manifests) && typeof record.manifests === 'object'
    ? record.manifests as Record<string, any>
    : {}
  const labels = Object.keys(manifests)
  if (!labels.length) return emptyResult(hash)

  const activeLabel = typeof record.active_manifest === 'string'
    ? record.active_manifest
    : typeof record.activeManifest === 'string' ? record.activeManifest : labels[0]
  const active = manifests[activeLabel] && typeof manifests[activeLabel] === 'object' ? manifests[activeLabel] : {}
  const failures = record.validation_results?.activeManifest?.failure
  const currentFailures = Array.isArray(failures) ? failures : []
  const legacyFailures = [record.validation_status, record.validationStatus]
    .flat()
    .filter((item: any) => item && item.success === false)
  const validationIssues = [...currentFailures, ...legacyFailures].map(issueText)
  const validationState = String(record.validation_state || record.validationState || '').toLowerCase()
  const trustOnly = validationIssues.length > 0 && validationIssues.every(issue => /untrusted|not trusted|trust list|certificate chain/i.test(issue))
  const invalid = validationState === 'invalid' || (validationIssues.length > 0 && !trustOnly)
  const assertions = Array.isArray(active.assertions) ? active.assertions : []
  const generatorInfo = Array.isArray(active.claim_generator_info) ? active.claim_generator_info[0] : undefined
  const claimGenerator = String(active.claim_generator || active.claimGenerator || generatorInfo?.name || '')

  return {
    verdict: invalid ? 'invalid' : trustOnly ? 'inconclusive' : 'verified',
    hasManifest: true,
    manifestCount: labels.length,
    activeManifest: activeLabel,
    claimGenerator,
    sourceType: findSourceType(assertions),
    validationIssues,
    timeline: extractTimeline(assertions, claimGenerator),
    hash,
  }
}

export async function sha256Blob(blob: Blob): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', await blob.arrayBuffer())
  return Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, '0')).join('')
}

function inferMime(name: string): string {
  if (/\.png$/i.test(name)) return 'image/png'
  if (/\.webp$/i.test(name)) return 'image/webp'
  if (/\.tiff?$/i.test(name)) return 'image/tiff'
  return 'image/jpeg'
}

export async function verifyC2paFile(file: File): Promise<C2paVerificationResult> {
  const hash = await sha256Blob(file)
  const c2pa = await getC2pa()
  const reader = await c2pa.reader.fromBlob(file.type || inferMime(file.name), file)
  if (!reader) return emptyResult(hash)
  try {
    return normalizeC2paStore(await reader.manifestStore(), hash)
  } finally {
    await reader.free()
  }
}
