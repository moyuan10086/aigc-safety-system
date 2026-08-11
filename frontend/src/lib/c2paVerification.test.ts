import { describe, expect, it } from 'vitest'
import { normalizeC2paStore, sha256Blob } from './c2paVerification'

describe('normalizeC2paStore', () => {
  it('marks a readable manifest without validation failures as verified', () => {
    const result = normalizeC2paStore({
      active_manifest: 'urn:c2pa:demo',
      manifests: {
        'urn:c2pa:demo': {
          claim_generator: 'Example Camera/1.0',
          assertions: [{
            label: 'c2pa.actions',
            data: { actions: [{ action: 'c2pa.created', when: '2026-08-11T08:00:00Z' }] },
          }],
        },
      },
      validation_state: 'valid',
    }, 'abc')

    expect(result.verdict).toBe('verified')
    expect(result.manifestCount).toBe(1)
    expect(result.claimGenerator).toBe('Example Camera/1.0')
    expect(result.timeline[0]?.action).toBe('c2pa.created')
  })

  it('marks reported validation failures as invalid', () => {
    const result = normalizeC2paStore({
      active_manifest: 'urn:c2pa:demo',
      manifests: { 'urn:c2pa:demo': {} },
      validation_results: {
        activeManifest: { failure: [{ code: 'claimSignature.mismatch' }] },
      },
    }, 'abc')

    expect(result.verdict).toBe('invalid')
    expect(result.validationIssues).toEqual(['claimSignature.mismatch'])
  })

  it('separates an untrusted signer from a tampered credential', () => {
    const result = normalizeC2paStore({
      active_manifest: 'urn:c2pa:demo',
      manifests: { 'urn:c2pa:demo': {} },
      validation_results: {
        activeManifest: { failure: [{ explanation: 'signing certificate untrusted' }] },
      },
    }, 'abc')

    expect(result.verdict).toBe('inconclusive')
    expect(result.validationIssues).toEqual(['signing certificate untrusted'])
  })

  it('returns not-found for an empty or malformed manifest store', () => {
    expect(normalizeC2paStore({}, 'abc').verdict).toBe('not-found')
    expect(normalizeC2paStore({ manifests: [] }, 'abc').verdict).toBe('not-found')
  })
})

describe('sha256Blob', () => {
  it('calculates the file hash locally', async () => {
    await expect(sha256Blob(new Blob(['abc']))).resolves.toBe(
      'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad',
    )
  })
})
