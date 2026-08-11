import { describe, expect, it } from 'vitest'
import { getProviderAttribution } from './providerAttribution'

describe('getProviderAttribution', () => {
  it('confirms OpenAI AI generation when a valid credential is signed by the media service', () => {
    const result = getProviderAttribution('OpenAI Media Service API', '', true)

    expect(result.provider).toBe('OpenAI')
    expect(result.aiGenerated).toBe(true)
    expect(result.title).toBe('OpenAI AI 生成内容')
    expect(result.note).toContain('OpenAI Media Service API')
    expect(result.note).toContain('具体模型')
  })

  it('does not call a generic C2PA library AI-generated without an AI source declaration', () => {
    const result = getProviderAttribution('Google C2PA Core Generator Library', '', true)

    expect(result.provider).toBe('Google')
    expect(result.aiGenerated).toBe(false)
    expect(result.title).toBe('Google C2PA 工具链')
  })

  it('confirms AI generation from an explicit trained algorithmic media declaration', () => {
    const result = getProviderAttribution('Example Generator', 'trainedAlgorithmicMedia', true)

    expect(result.aiGenerated).toBe(true)
    expect(result.title).toBe('AI 生成内容')
  })

  it('does not invent a provider from an unknown claim generator', () => {
    const result = getProviderAttribution('claim_v2_unit_test', '', true)

    expect(result.provider).toBe('未知')
    expect(result.aiGenerated).toBe(false)
  })
})
