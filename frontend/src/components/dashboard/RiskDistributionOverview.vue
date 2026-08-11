<template>
  <section v-if="total" class="risk-overview" aria-label="风险类别统计">
    <figure class="risk-donut">
      <BaseChart :option="chartOption" :aria-label="`风险类别分布，总计 ${total} 次`" />
      <figcaption><strong>{{ total }}</strong><span>风险总量</span></figcaption>
    </figure>

    <section class="risk-ranking" aria-label="风险类别排行">
      <header><strong>类别排行</strong><span>占比 / 次数</span></header>
      <ol>
        <li v-for="(item, index) in visibleItems" :key="item.name" :style="{ '--risk-color': item.color }">
          <span class="rank">{{ String(index + 1).padStart(2, '0') }}</span>
          <span class="category" :title="item.name">{{ item.name }}</span>
          <strong>{{ item.percent }}%</strong>
          <small>{{ item.value }} 次</small>
          <i><b :style="{ width: `${Math.max(item.percent, 3)}%` }"></b></i>
        </li>
      </ol>
    </section>
  </section>

  <section v-else class="risk-empty">
    <ShieldCheck :size="28" stroke-width="1.5" />
    <strong>当前窗口暂无风险分类</strong>
    <span>检测到风险类别后将在此生成分布统计</span>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { EChartsCoreOption } from 'echarts/core'
import { ShieldCheck } from 'lucide-vue-next'
import BaseChart from './BaseChart.vue'

type RiskItem = { name: string; value: number }
type DisplayItem = RiskItem & { color: string; percent: number }

const props = defineProps<{ items: RiskItem[] }>()

const categoryNames: Record<string, string> = {
  jailbreak: '越狱攻击',
  prompt_injection: '提示词注入',
  prompt_injection_and_jailbreak: '提示词攻击',
  cyber_abuse: '网络攻击滥用',
  weapons_violence: '武器与暴力',
  self_harm: '自伤风险',
  sexual_content: '色情内容',
  adult_content: '成人内容',
  child_safety: '未成年人安全',
  personal_data: '隐私数据',
  sensitive_data: '敏感数据',
  illegal_activity: '违法活动',
  agent_security: 'Agent 安全',
  agent_tool_abuse: '工具调用滥用',
  weapon_display: '武器展示',
  violence: '暴力血腥',
  graphic_violence: '暴力血腥',
  political_sensitive: '政治敏感',
  policy_violation: '策略违规',
  marketing_violation: '营销违规',
  misinformation: '虚假信息',
  unsafe: '不安全内容',
  unclassified: '未分类风险',
}

const palette = ['#d13c4f', '#bf720d', '#087eae', '#16805e', '#7356a8', '#607586']

const normalizedItems = computed<RiskItem[]>(() => {
  const grouped = new Map<string, number>()
  for (const item of props.items) {
    const value = Number(item.value) || 0
    if (value <= 0) continue
    const name = categoryNames[item.name] || readableFallback(item.name)
    grouped.set(name, (grouped.get(name) || 0) + value)
  }
  return [...grouped].map(([name, value]) => ({ name, value })).sort((a, b) => b.value - a.value)
})

const total = computed(() => normalizedItems.value.reduce((sum, item) => sum + item.value, 0))

const visibleItems = computed<DisplayItem[]>(() => {
  const leading = normalizedItems.value.slice(0, 5)
  const remaining = normalizedItems.value.slice(5).reduce((sum, item) => sum + item.value, 0)
  const items = remaining ? [...leading, { name: '其他风险', value: remaining }] : leading
  return items.map((item, index) => ({
    ...item,
    color: palette[index % palette.length],
    percent: total.value ? Math.round(item.value / total.value * 1000) / 10 : 0,
  }))
})

const chartOption = computed<EChartsCoreOption>(() => ({
  animationDuration: 650,
  tooltip: {
    trigger: 'item',
    confine: true,
    formatter: ({ name, value, percent }: { name: string; value: number; percent: number }) => `${name}<br/><b>${value} 次</b> · ${percent}%`,
  },
  series: [{
    type: 'pie',
    radius: ['57%', '78%'],
    center: ['50%', '50%'],
    startAngle: 90,
    clockwise: true,
    minAngle: 3,
    avoidLabelOverlap: true,
    label: { show: false },
    labelLine: { show: false },
    emphasis: { scale: true, scaleSize: 4 },
    itemStyle: { borderColor: '#ffffff', borderWidth: 3, borderRadius: 3 },
    data: visibleItems.value.map(item => ({ name: item.name, value: item.value, itemStyle: { color: item.color } })),
  }],
}))

function readableFallback(value: string) {
  const cleaned = String(value || '').trim().replace(/[_-]+/g, ' ')
  return cleaned && !/^[a-z\s]+$/i.test(cleaned) ? cleaned : '其他风险'
}
</script>

<style scoped>
.risk-overview{height:258px;display:grid;grid-template-columns:minmax(126px,42%) minmax(0,1fr);align-items:center;gap:14px}.risk-donut{position:relative;width:100%;height:190px;margin:0}.risk-donut figcaption{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;flex-direction:column;pointer-events:none}.risk-donut figcaption strong{color:var(--text);font-size:25px;line-height:1;font-weight:750;font-variant-numeric:tabular-nums}.risk-donut figcaption span{margin-top:6px;color:var(--faint);font-size:9px}.risk-ranking{min-width:0}.risk-ranking>header{height:28px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid var(--line)}.risk-ranking>header strong{color:var(--muted);font-size:10px;font-weight:650}.risk-ranking>header span{color:var(--faint);font-size:8px}.risk-ranking ol{display:flex;flex-direction:column;gap:4px;margin:8px 0 0;padding:0;list-style:none}.risk-ranking li{position:relative;display:grid;grid-template-columns:22px minmax(0,1fr) 38px 38px;align-items:center;column-gap:5px;min-height:31px;padding-bottom:6px}.rank{color:var(--faint);font:700 8px/1 ui-monospace,monospace}.category{min-width:0;color:var(--text);font-size:10px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.risk-ranking li>strong{color:var(--risk-color);font-size:10px;text-align:right;font-variant-numeric:tabular-nums}.risk-ranking li>small{color:var(--muted);font-size:8px;text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}.risk-ranking li>i{position:absolute;left:27px;right:0;bottom:1px;height:3px;overflow:hidden;background:var(--surface-3);border-radius:2px}.risk-ranking li>i b{display:block;height:100%;background:var(--risk-color);border-radius:2px}.risk-empty{height:258px;display:flex;align-items:center;justify-content:center;flex-direction:column;color:var(--success);text-align:center}.risk-empty strong{margin-top:10px;color:var(--text);font-size:11px}.risk-empty span{margin-top:5px;color:var(--faint);font-size:9px}@container (max-width:360px){.risk-overview{grid-template-columns:116px minmax(0,1fr);gap:8px}.risk-donut{height:166px}.risk-ranking li{grid-template-columns:18px minmax(0,1fr) 34px}.risk-ranking li>small{display:none}.risk-ranking li>i{left:23px}}
</style>
