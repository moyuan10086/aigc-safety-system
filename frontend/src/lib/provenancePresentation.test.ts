import { describe, expect, it } from 'vitest'
import { getProvenancePresentation } from './provenancePresentation'

describe('getProvenancePresentation', () => {
  it('explains a confirmed source instead of showing only a badge', () => {
    const presentation = getProvenancePresentation('confirmed_source')

    expect(presentation.label).toBe('检测到来源凭证')
    expect(presentation.message).toContain('Content Credentials')
    expect(presentation.message).toContain('不能据此确认具体 AI 厂商或模型')
  })
})
