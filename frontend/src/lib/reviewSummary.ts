export function contentMetricTone(verdict?: string): string {
  if (!verdict) return ''
  if (verdict === 'safe') return 'metric-success'
  if (verdict === 'unsafe') return 'metric-danger'
  return 'metric-warn'
}

export function provenanceMetricTone(aiGenerated: boolean): string {
  return aiGenerated ? 'metric-success' : ''
}
