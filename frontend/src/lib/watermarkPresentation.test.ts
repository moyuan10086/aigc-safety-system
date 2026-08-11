import { describe, expect, it } from 'vitest'
import { getVisibleWatermarkCapabilities, getWatermarkPresentation } from './watermarkPresentation'

describe('getWatermarkPresentation', () => {
  it('treats a signed platform AI watermark as confirmed platform evidence', () => {
    const result = getWatermarkPresentation({
      status: 'confirmed',
      provider: 'aigc-safety',
      payload: { content_id: 'img-001', content_type: 'ai_generated' },
      signature_valid: true,
    })

    expect(result.aiGenerated).toBe(true)
    expect(result.title).toBe('本平台 AI 标识已验证')
    expect(result.badge).toBe('平台水印有效')
  })

  it('does not treat no signal as human-created content', () => {
    const result = getWatermarkPresentation({ status: 'no_signal' })

    expect(result.aiGenerated).toBe(false)
    expect(result.title).toBe('未检出平台水印')
    expect(result.note).toContain('不代表非 AI')
  })

  it('marks invalid signed signal for manual review', () => {
    const result = getWatermarkPresentation({ status: 'invalid', tamper_suspected: true })

    expect(result.invalid).toBe(true)
    expect(result.badge).toBe('水印无效')
  })

  it('hides unconfigured and inapplicable provider capabilities', () => {
    const visible = getVisibleWatermarkCapabilities([
      { id: 'platform_dct', label: '平台签名隐形水印', status: 'available' },
      { id: 'synthid', label: 'Google SynthID', status: 'not_configured' },
      { id: 'audioseal', label: 'Meta AudioSeal', status: 'unsupported_media' },
    ])

    expect(visible.map(item => item.id)).toEqual(['platform_dct'])
  })
})
