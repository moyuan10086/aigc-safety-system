export function getProvenancePresentation(state: string): { label: string; message: string } {
  const presentations: Record<string, { label: string; message: string }> = {
    confirmed_source: {
      label: '检测到来源凭证',
      message: '已验证 Content Credentials 与当前文件的绑定关系，说明文件带有可验证来源链；不能据此确认具体 AI 厂商或模型。',
    },
    not_found: {
      label: '未发现来源证据',
      message: '未发现兼容水印或来源声明，不代表该图片一定不是 AI 生成。',
    },
    inconclusive: {
      label: '来源不确定',
      message: '当前来源证据不足，不能确认来源，请结合内容检测并转人工复核。',
    },
    invalid_or_tampered: {
      label: '来源需复核',
      message: '来源声明验证失败或资产可能被篡改，应提升风险并转人工复核。',
    },
  }
  return presentations[state] || { label: '来源状态未知', message: '当前结果无法映射到已知来源状态，请人工复核。' }
}
