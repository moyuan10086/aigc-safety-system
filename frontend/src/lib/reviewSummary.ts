export function contentMetricTone(verdict?: string): string {
  if (!verdict) return ''
  if (verdict === 'safe') return 'metric-success'
  if (verdict === 'unsafe') return 'metric-danger'
  return 'metric-warn'
}

export function provenanceMetricTone(aiGenerated: boolean): string {
  return aiGenerated ? 'metric-success' : ''
}

type DeepfakeEvidence = {
  label?: string
  score?: number
}

type MllmEvidence = {
  verdict?: string
  confidence?: number
  status?: string
}

export type AuthenticitySummary = {
  title: string
  note: string
  tone: string
  requiresReview: boolean
}

const percent = (value?: number): string =>
  typeof value === 'number' && Number.isFinite(value)
    ? `${Math.round(Math.max(0, Math.min(1, value)) * 100)}%`
    : '—'

export function authenticitySummary(
  deepfake?: DeepfakeEvidence,
  mllm?: MllmEvidence,
): AuthenticitySummary {
  const deepfakeVerdict = deepfake?.label === 'fake'
    ? 'fake'
    : deepfake?.label === 'real'
      ? 'real'
      : deepfake?.label === 'review'
        ? 'uncertain'
      : deepfake?.label === 'skipped'
        ? 'skipped'
        : 'missing'
  const mllmVerdict = mllm?.status === 'degraded'
    ? 'uncertain'
    : mllm?.verdict === 'fake' || mllm?.verdict === 'real'
      ? mllm.verdict
      : mllm
        ? 'uncertain'
        : 'missing'
  const deepfakeNote = `Deepfake ${percent(deepfake?.score)}`
  const mllmNote = `MLLM ${percent(mllm?.confidence)}`

  if (deepfakeVerdict === 'missing' && mllmVerdict === 'missing') {
    return { title: '未选择', note: '本次未运行真实性检测', tone: '', requiresReview: false }
  }

  if (
    (deepfakeVerdict === 'fake' && mllmVerdict === 'real')
    || (deepfakeVerdict === 'real' && mllmVerdict === 'fake')
  ) {
    return {
      title: '模型分歧',
      note: `${deepfakeNote} · ${mllmNote} · 转人工复核`,
      tone: 'metric-warn',
      requiresReview: true,
    }
  }

  if (deepfakeVerdict === 'fake' && mllmVerdict === 'fake') {
    return {
      title: '高度疑似伪造',
      note: `${deepfakeNote} · ${mllmNote} · 双模型一致`,
      tone: 'metric-danger',
      requiresReview: true,
    }
  }

  if (deepfakeVerdict === 'fake' || mllmVerdict === 'fake') {
    const source = deepfakeVerdict === 'fake' ? deepfakeNote : mllmNote
    const other = deepfakeVerdict === 'fake' ? mllmVerdict : deepfakeVerdict
    const otherNote = other === 'skipped'
      ? 'Deepfake 不适用'
      : other === 'uncertain'
        ? deepfakeVerdict === 'fake' ? 'MLLM 不确定' : 'Deepfake 待复核'
        : deepfakeVerdict === 'fake' ? 'MLLM 未运行' : 'Deepfake 未运行'
    return {
      title: deepfakeVerdict === 'fake' ? '疑似人脸伪造' : '疑似 AI 生成',
      note: `${source} · ${otherNote} · 转人工复核`,
      tone: 'metric-danger',
      requiresReview: true,
    }
  }

  if (deepfakeVerdict === 'real' && mllmVerdict === 'real') {
    return {
      title: '倾向真实',
      note: `${deepfakeNote} · ${mllmNote} · 双模型一致`,
      tone: 'metric-success',
      requiresReview: false,
    }
  }

  if (deepfakeVerdict === 'skipped' && mllmVerdict === 'real') {
    return {
      title: 'MLLM 倾向真实',
      note: `${mllmNote} · Deepfake 不适用`,
      tone: 'metric-success',
      requiresReview: false,
    }
  }

  return {
    title: '证据不完整',
    note: `${deepfakeVerdict === 'missing' ? 'Deepfake 未运行' : deepfakeVerdict === 'uncertain' ? 'Deepfake 待复核' : deepfakeNote} · ${mllmVerdict === 'missing' ? 'MLLM 未运行' : mllmVerdict === 'uncertain' ? 'MLLM 不确定' : mllmNote} · 转人工复核`,
    tone: 'metric-warn',
    requiresReview: true,
  }
}
