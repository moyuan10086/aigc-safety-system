import { describe, expect, it } from 'vitest'
import { contentMetricTone, provenanceMetricTone } from './reviewSummary'

describe('review summary metric tones', () => {
  it('does not highlight a module that was not run', () => {
    expect(contentMetricTone(undefined)).toBe('')
  })

  it('uses metric-only tones instead of reusable badge classes', () => {
    expect(contentMetricTone('safe')).toBe('metric-success')
    expect(contentMetricTone('review')).toBe('metric-warn')
    expect(contentMetricTone('unsafe')).toBe('metric-danger')
    expect(provenanceMetricTone(true)).toBe('metric-success')
  })
})
