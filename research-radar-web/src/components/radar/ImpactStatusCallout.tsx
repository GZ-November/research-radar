import type { Impact } from '@/types'
import { IMPACT_MODE, REVIEW_STATE, SEVERITY, STANCE } from '@/lib/labels'
import { useAppStore } from '@/store/AppStore'
import { Callout, type CalloutKind } from './Callout'
import { StatusBadge } from './StatusBadge'

// 采用指引 callout（render_impact_status 复刻）：徽章行 + 一条按优先级的指引
export function ImpactStatusCallout({ impact }: { impact: Impact }) {
  const { impactState } = useAppStore()
  const review = impactState(impact)

  let kind: CalloutKind = 'info'
  let text: string
  if (review === 'dismissed') {
    kind = 'info'
    text = '已选择不采用：相关自动行动已关闭；你仍可重新采用这项影响。'
  } else if (review === 'confirmed' || review === 'edited') {
    kind = 'success'
    text = '已采用：这个判断已进入证据账本，相关行动已转为可执行。'
  } else if (impact.trust_state === 'blocked') {
    kind = 'error'
    text = '暂不可采用：证据校验未通过，需要先补齐原文证据。'
  } else if (impact.impact_mode === 'no_material_change') {
    kind = 'success'
    text = '无需改变：条件矩阵和精确证据已保存；当前不要求修改实验、数据或写作。'
  } else if (impact.impact_mode === 'research_integrity' || impact.event_type === 'retraction') {
    kind = 'error'
    text = '建议采用（紧急）：用于重新验证引用和实验；采用后会打开重新验证行动。'
  } else if (impact.stance === 'challenges' && ['compatible', 'partial'].includes(impact.comparability)) {
    kind = 'warning'
    text = '建议采用：用于团队决策和条件匹配实验；不会自动改写你的 Claim。'
  } else if (impact.stance === 'supports' && ['compatible', 'partial'].includes(impact.comparability)) {
    kind = 'success'
    text = '建议采用为支持证据：用于 Discussion 和证据账本；仍需你确认引用方式。'
  } else if (
    ['boundary_condition', 'prior_art'].includes(impact.impact_mode) ||
    impact.comparability === 'incompatible'
  ) {
    kind = 'info'
    text = '建议部分采用：只用于补实验边界、Related Work 或 Limitations，不作为直接支持/反驳。'
  } else if (impact.stance === 'uncertain') {
    kind = 'warning'
    text = '先核对再采用：先检查原文条件和精确证据，再决定是否打开行动。'
  } else {
    kind = 'info'
    text = '建议作为背景采用：用于研究定位或后续观察，不会自动改变核心主张。'
  }

  return (
    <div>
      <div className="flex flex-wrap items-center gap-1.5">
        <StatusBadge k={impact.severity} label={SEVERITY[impact.severity]} />
        <StatusBadge k={impact.stance} label={STANCE[impact.stance]} />
        <StatusBadge tone="blue" label={IMPACT_MODE[impact.impact_mode]} />
        <StatusBadge k={review} label={REVIEW_STATE[review]} />
      </div>
      <Callout kind={kind} className="mt-2">
        {text}
      </Callout>
    </div>
  )
}
