# AIGC 安全驾驶舱组件选型记录（2026-08-06）

## 选型原则

- 优先选择 Vue 3、TypeScript、MIT/Apache-2.0 且能按需使用的项目。
- 业务视觉允许薄封装，但动画、数字滚动、图表和基础装饰优先复用成熟组件。
- 位图只承载真实风险样本；HUD、边框和中枢使用 SVG/Canvas/CSS，避免换屏后模糊。
- 真实指标与演示数据分层，视觉组件不得伪造业务状态。

## 子组件决策

| 子组件 | 采用方案 | 来源 | 使用方式 | 是否需要图片 |
| --- | --- | --- | --- | --- |
| 顶部 KPI 指标 | `CockpitMetric` + CountUp.js + Lucide | [IofTV-Screen-Vue3](https://github.com/daidaibg/IofTV-Screen-Vue3)、[CountUp.js](https://github.com/inorganik/countUp.js)、[Lucide](https://github.com/lucide-icons/lucide) | 业务薄封装；数字动画和图标来自开源库 | 否 |
| 标题两翼装饰 | DataV `Decoration8` | [vaemusic/datav-vue3](https://github.com/vaemusic/datav-vue3) | npm 组件直接引用 | 否 |
| 中央安全中枢 | DataV `Decoration9` + 现有审核链 SVG | [vaemusic/datav-vue3](https://github.com/vaemusic/datav-vue3) | DataV 负责双向旋转能量环；业务节点和连线保留现有实现 | 否 |
| HUD 面板边框 | 现有 `CockpitPanel`，参考 DataV `BorderBox13` | [IofTV-Screen-Vue3](https://github.com/daidaibg/IofTV-Screen-Vue3) | 不整体替换，避免破坏当前裁切和响应式；后续按面板逐个迁移 | 否 |
| 趋势、环图、雷达 | ECharts 6 | [Apache ECharts](https://github.com/apache/echarts) | 保留当前按需注册与 `ResizeObserver` | 否 |
| 实时告警列表 | 当前业务列表；候选 DataV `ScrollBoard` | [vaemusic/datav-vue3](https://github.com/vaemusic/datav-vue3) | 当前列表支持真实字段和脱敏 IP，暂不换成通用滚动表 | 否 |
| 风险样本条 | 当前 `RiskSampleStrip` | 系统实测样本目录 | 业务专用组件，包含风险框、脱敏、处置状态和悬停暂停 | 是，必须是真实/授权/明确标注的演示样本 |
| 大屏缩放 | 当前响应式网格 + ResizeObserver；候选 IofTV `scale-screen` / `v-scale-screen` | [IofTV-Screen-Vue3](https://github.com/daidaibg/IofTV-Screen-Vue3)、[v-scale-screen](https://www.npmjs.com/package/v-scale-screen) | 目前 1024、1366、1920 已实测；暂不引入整屏等比缩放，避免小屏文字被整体压小 | 否 |
| 地理态势 | ECharts Map + GeoJSON，后端 GeoIP 缓存 | [ECharts](https://github.com/apache/echarts)、[go-view](https://github.com/dromara/go-view) | 等真实公网 IP 地理数据契约完成后再加入；内网 IP 只标为内部来源 | 可选地图纹理，不使用固定数据截图 |

## 仓库评估

- `daidaibg/IofTV-Screen-Vue3`：MIT，技术栈与本项目接近，适合复用数字动画、缩放容器和布局思路。
- `vaemusic/datav-vue3` / `@kjgl77/datav-vue3`：MIT，提供 Decoration、BorderBox、DigitalFlop、ScrollBoard 等 Vue 3 组件。本次已引入 `Decoration8/9`。
- `dromara/go-view`：MIT，组件覆盖全面，但属于低代码平台，整套引入会带入编辑器、Naive UI、Three.js 等大量依赖，只参考组件组织、地图和图标方案。
- `DataV-Team/DataV-Vue3`：MIT，但仍标记 WIP/alpha，不作为比赛部署主依赖。
- `yyhsong/iDataV`：最后代码提交较早且 GitHub 未声明许可证，不复制其代码。
- React 大屏仓库：不引入，避免为了少量视觉组件增加第二套前端运行时。

## 当前落地结果

- 六个 KPI 均有独立业务图标、六边形状态徽章、分组数字和风险色。
- 标题装饰、中枢能量环来自 DataV 组件，业务审核链仍保持可解释结构。
- 已验证 `1920x1080`、`1366x768`、`1024x640`；紧凑屏幕会缩小中枢和能力卡，并隐藏重复状态说明，不隐藏核心业务图标。
- 生产地址：<https://aigc.49.51.248.227.sslip.io/dashboard/screen>
