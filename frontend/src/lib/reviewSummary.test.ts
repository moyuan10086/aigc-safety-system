import { describe, expect, it } from 'vitest'
import { authenticitySummary, contentMetricTone, provenanceMetricTone } from './reviewSummary'

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

describe('authenticity evidence summary', () => {
  it('escalates conflicting Deepfake and MLLM conclusions to review', () => {
    expect(authenticitySummary(
      { label: 'real', score: 0.401 },
      { verdict: 'fake', confidence: 0.99, status: 'completed' },
    )).toEqual({
      title: '模型分歧',
      note: 'Deepfake 40% · MLLM 99% · 转人工复核',
      tone: 'metric-warn',
      requiresReview: true,
    })
  })

  it('reports a high-risk consensus without treating confidence as accuracy', () => {
    const summary = authenticitySummary(
      { label: 'fake', score: 0.82 },
      { verdict: 'fake', confidence: 0.91, status: 'completed' },
    )
    expect(summary.title).toBe('高度疑似伪造')
    expect(summary.note).toContain('双模型一致')
    expect(summary.tone).toBe('metric-danger')
  })

  it('uses MLLM when Deepfake is not applicable', () => {
    expect(authenticitySummary(
      { label: 'skipped', score: 0 },
      { verdict: 'fake', confidence: 0.88, status: 'completed' },
    )).toMatchObject({
      title: '疑似 AI 生成',
      tone: 'metric-danger',
      requiresReview: true,
    })
  })

  it('preserves the Deepfake review state instead of treating it as real', () => {
    expect(authenticitySummary(
      { label: 'review', score: 0.3308 },
      { verdict: 'fake', confidence: 0.99, status: 'completed' },
    )).toEqual({
      title: '疑似 AI 生成',
      note: 'MLLM 99% · Deepfake 待复核 · 转人工复核',
      tone: 'metric-danger',
      requiresReview: true,
    })
  })

  it('does not silently treat an unavailable expert as safe', () => {
    expect(authenticitySummary(
      { label: 'real', score: 0.2 },
      { verdict: 'uncertain', confidence: 0, status: 'degraded' },
    )).toMatchObject({
      title: '证据不完整',
      tone: 'metric-warn',
      requiresReview: true,
    })
  })

  it('shows a real-leaning conclusion only when both models agree', () => {
    expect(authenticitySummary(
      { label: 'real', score: 0.18 },
      { verdict: 'real', confidence: 0.84, status: 'completed' },
    )).toMatchObject({
      title: '倾向真实',
      tone: 'metric-success',
      requiresReview: false,
    })
  })
})
