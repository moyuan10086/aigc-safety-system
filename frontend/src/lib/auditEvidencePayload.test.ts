import { describe, expect, it } from 'vitest'
import { buildAuditEvidencePayload } from './auditEvidencePayload'

describe('buildAuditEvidencePayload', () => {
  it('records completed results and explicitly marks missing modules as not run', () => {
    const payload = buildAuditEvidencePayload({
      eventId: 'evt-1', sampleName: 'sample.png', reportId: 'report-1', customNote: '人工备注',
      results: {
        deepfake: { label: 'fake', score: 0.82, model: 'xception' },
        provenance: { overall_state: 'confirmed_source', source_evidence: { content_credentials: { claim_generator: 'OpenAI' } } },
      },
    })

    expect(payload.report_id).toBe('report-1')
    expect(payload.deepfake).toMatchObject({ status: 'completed', label: 'fake', score: 0.82 })
    expect(payload.provenance).toMatchObject({ status: 'completed', state: 'confirmed_source', provider: 'OpenAI' })
    expect(payload.content_safety.status).toBe('not_run')
    expect(payload.custom_note).toBe('人工备注')
  })
})
