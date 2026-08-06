/* ============================================================
   大屏图表主题 · 与 styles/screen-tokens.css 共用同一套颜色语义
   Canvas 无法直接使用 CSS 变量，因此运行时从 .big-screen 读取令牌，
   读取失败（例如图表在大屏挂载前初始化）时回落到此处的常量。
   ============================================================ */

const FALLBACK: Record<string, string> = {
  '--sc-ink': '#eef8ff',
  '--sc-ink-2': '#c3dded',
  '--sc-ink-3': '#8fb2c7',
  '--sc-ink-4': '#62889e',
  '--sc-accent': '#2ac9ff',
  '--sc-cyan': '#22e3d8',
  '--sc-violet': '#8f7dff',
  '--sc-mint': '#3ce8aa',
  '--sc-safe': '#3ce8aa',
  '--sc-low': '#38c8f0',
  '--sc-medium': '#ffb545',
  '--sc-high': '#ff7a45',
  '--sc-critical': '#ff4363',
  '--sc-line-2': 'rgba(74,166,214,.30)',
  '--sc-line-soft': 'rgba(74,166,214,.11)',
}

const cache = new Map<string, string>()

/** 读取大屏令牌；结果缓存，避免每帧 getComputedStyle。 */
export function token(name: string): string {
  const hit = cache.get(name)
  if (hit) return hit
  let value = ''
  if (typeof document !== 'undefined') {
    const host = document.querySelector('.big-screen')
    if (host) value = getComputedStyle(host).getPropertyValue(name).trim()
  }
  const resolved = value || FALLBACK[name] || '#2ac9ff'
  if (value) cache.set(name, resolved)
  return resolved
}

/** 令牌可能在主题切换后变化，此处提供显式失效入口。 */
export function resetTokenCache() {
  cache.clear()
}

/** 风险等级 → 语义色，图表与状态点共用，保证同一风险在全屏一致。 */
export type RiskLevel = 'safe' | 'low' | 'medium' | 'high' | 'critical'

export function riskColor(level: RiskLevel): string {
  return token(`--sc-${level}`)
}

/** 风险类别按危害度归档，让环形图颜色本身承载严重程度信息。 */
const CATEGORY_LEVEL: Record<string, RiskLevel> = {
  child_safety: 'critical',
  weapons_violence: 'critical',
  self_harm: 'critical',
  illegal_activity: 'critical',
  graphic_violence: 'high',
  sexual_content: 'high',
  adult_content: 'high',
  weapon_display: 'high',
  jailbreak: 'high',
  prompt_injection: 'high',
  personal_data: 'medium',
  cyber_abuse: 'medium',
  political_sensitive: 'medium',
  agent_security: 'medium',
  marketing_violation: 'low',
}

export function categoryLevel(name: string): RiskLevel {
  return CATEGORY_LEVEL[name] || 'low'
}

/** 类别序列色：同级别按明度轻微错开，避免相邻扇区糊成一片。 */
export function categoryColor(name: string, index: number): string {
  const base = riskColor(categoryLevel(name))
  const tilt = index % 3
  if (tilt === 0) return base
  return mix(base, tilt === 1 ? '#ffffff' : '#0b2135', tilt === 1 ? 0.18 : 0.16)
}

/** 简易色彩混合，用于生成同色系深浅变体（不引入额外依赖）。 */
export function mix(from: string, to: string, ratio: number): string {
  const a = parseColor(from)
  const b = parseColor(to)
  if (!a || !b) return from
  const channel = (x: number, y: number) => Math.round(x + (y - x) * ratio)
  return `rgb(${channel(a[0], b[0])},${channel(a[1], b[1])},${channel(a[2], b[2])})`
}

function parseColor(value: string): [number, number, number] | null {
  const text = value.trim()
  if (text.startsWith('#')) {
    const hex = text.length === 4
      ? text.slice(1).split('').map(c => c + c).join('')
      : text.slice(1, 7)
    const int = Number.parseInt(hex, 16)
    if (Number.isNaN(int)) return null
    return [(int >> 16) & 255, (int >> 8) & 255, int & 255]
  }
  const parts = text.match(/[\d.]+/g)
  if (!parts || parts.length < 3) return null
  return [Number(parts[0]), Number(parts[1]), Number(parts[2])]
}

/** rgba 化，用于渐变与半透明填充。 */
export function alpha(value: string, opacity: number): string {
  const rgb = parseColor(value)
  if (!rgb) return value
  return `rgba(${rgb[0]},${rgb[1]},${rgb[2]},${opacity})`
}

/** 折线面积渐变：顶部高亮、底部隐入背景。 */
export function areaGradient(color: string, top = 0.34) {
  return {
    type: 'linear' as const,
    x: 0, y: 0, x2: 0, y2: 1,
    colorStops: [
      { offset: 0, color: alpha(color, top) },
      { offset: 0.55, color: alpha(color, top * 0.34) },
      { offset: 1, color: alpha(color, 0) },
    ],
  }
}

/** 统一坐标轴：细线、弱标签、无多余轴线。 */
export function axisBase() {
  return {
    axisLine: { lineStyle: { color: token('--sc-line-2') } },
    axisTick: { show: false },
    axisLabel: {
      color: token('--sc-ink-3'),
      fontSize: 11,
      fontFamily: 'Inter, "Roboto Mono", ui-monospace, monospace',
    },
  }
}

/** 统一 tooltip：深色玻璃卡 + 高亮描边，替换 ECharts 默认白底。 */
export function tooltipBase() {
  return {
    backgroundColor: 'rgba(4,18,32,.94)',
    borderColor: token('--sc-line-2'),
    borderWidth: 1,
    padding: [8, 11] as [number, number],
    textStyle: { color: token('--sc-ink-2'), fontSize: 12 },
    extraCssText: 'backdrop-filter:blur(8px);border-radius:8px;box-shadow:0 12px 30px -10px rgba(0,0,0,.8);',
  }
}
