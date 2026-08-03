import { use } from 'echarts/core'
import { BarChart, GraphChart, LineChart, MapChart, PieChart, RadarChart } from 'echarts/charts'
import {
  AriaComponent,
  GeoComponent,
  GridComponent,
  LegendComponent,
  TitleComponent,
  TooltipComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

use([
  BarChart,
  GraphChart,
  LineChart,
  MapChart,
  PieChart,
  RadarChart,
  AriaComponent,
  GeoComponent,
  GridComponent,
  LegendComponent,
  TitleComponent,
  TooltipComponent,
  CanvasRenderer,
])
