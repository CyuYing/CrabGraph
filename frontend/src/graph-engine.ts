import { use } from 'echarts/core'
import { GraphChart } from 'echarts/charts'
import { TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
use([GraphChart, TooltipComponent, CanvasRenderer])
export { init } from 'echarts/core'
