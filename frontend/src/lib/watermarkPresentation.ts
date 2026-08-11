export interface WatermarkEvidence {
  status?: string
  provider?: string
  payload?: { content_id?: string; content_type?: string } | null
  signature_valid?: boolean
  tamper_suspected?: boolean
  note?: string
}

export interface WatermarkCapability {
  id: string
  label: string
  status: string
  note?: string
}

export const getVisibleWatermarkCapabilities = (items?: WatermarkCapability[] | null) =>
  Array.isArray(items) ? items.filter(item => item.status === 'available') : []

export const getWatermarkPresentation = (evidence?: WatermarkEvidence | null) => {
  const status = evidence?.status || 'not_configured'
  if (status === 'confirmed') {
    const aiGenerated = evidence?.payload?.content_type === 'ai_generated'
    return {
      status,
      aiGenerated,
      invalid: false,
      title: aiGenerated ? '本平台 AI 标识已验证' : '本平台算法增强标识已验证',
      badge: '平台水印有效',
      note: evidence?.note || '已验证本平台签名隐形水印',
    }
  }
  if (status === 'invalid') {
    return {
      status,
      aiGenerated: false,
      invalid: true,
      title: '平台水印需要复核',
      badge: '水印无效',
      note: evidence?.note || '检测到水印信号，但签名或载荷校验失败',
    }
  }
  if (status === 'no_signal') {
    return {
      status,
      aiGenerated: false,
      invalid: false,
      title: '未检出平台水印',
      badge: '无平台信号',
      note: evidence?.note || '未检出本平台隐形水印；不代表非 AI 生成',
    }
  }
  return {
    status,
    aiGenerated: false,
    invalid: false,
    title: '平台水印核验未配置',
    badge: '未配置',
    note: evidence?.note || '当前部署未配置平台隐形水印核验密钥',
  }
}
