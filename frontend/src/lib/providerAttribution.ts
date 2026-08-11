export interface ProviderAttribution {
  provider: string
  title: string
  aiGenerated: boolean
  note: string
}

const providers: Array<{ match: RegExp; name: string; title: string }> = [
  { match: /google|gemini|imagen/i, name: 'Google', title: 'Google C2PA 工具链' },
  { match: /openai|chatgpt|dall[- ]?e/i, name: 'OpenAI', title: 'OpenAI 工具链' },
  { match: /midjourney/i, name: 'Midjourney', title: 'Midjourney 工具链' },
  { match: /adobe|photoshop|firefly/i, name: 'Adobe', title: 'Adobe 工具链' },
  { match: /stability|stable diffusion/i, name: 'Stability AI', title: 'Stability AI 工具链' },
]

export function getProviderAttribution(claimGenerator: string, sourceType = '', credentialsValid = false): ProviderAttribution {
  const value = claimGenerator.trim()
  const match = providers.find(item => item.match.test(value))
  const explicitAiSource = /trainedAlgorithmicMedia/i.test(sourceType)
  const openAiMediaService = /OpenAI Media Service API/i.test(value)
  const aiGenerated = credentialsValid && (explicitAiSource || openAiMediaService)

  if (aiGenerated) {
    const provider = match?.name || '未知厂商'
    return {
      provider,
      title: match ? `${provider} AI 生成内容` : 'AI 生成内容',
      aiGenerated: true,
      note: openAiMediaService
        ? '有效 C2PA 凭证由 OpenAI Media Service API 签发，可确认该文件来自 OpenAI 的 AI 媒体生成服务；凭证未披露具体模型名称。'
        : `有效 C2PA 凭证将数字来源声明为训练算法生成内容${match ? `，签发工具归属于 ${provider}` : ''}；凭证未披露具体模型名称。`,
    }
  }

  if (!match) {
    return {
      provider: '未知',
      title: value ? '未识别的签发工具' : '未提供签发工具',
      aiGenerated: false,
      note: '凭证没有提供可归因到具体厂商或模型的签发信息。',
    }
  }
  return {
    provider: match.name,
    title: match.title,
    aiGenerated: false,
    note: `已识别 ${match.name} 的 C2PA 签发工具链，但当前凭证没有明确声明该内容由训练算法生成。`,
  }
}
