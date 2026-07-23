// 标签字典（BUILD_SPEC §3 逐字复用）+ 徽章配色映射
import type {
  ActionStatus,
  ActionType,
  ApprovalState,
  Centrality,
  Comparability,
  ConditionStatus,
  EditClass,
  ImpactMode,
  Priority,
  ReviewState,
  ScanStatus,
  Severity,
  Stance,
  SuggestedAction,
  TrustState,
} from '@/types'

export type Tone = 'red' | 'orange' | 'blue' | 'green' | 'yellow' | 'gray' | 'teal'

export const SEVERITY: Record<Severity, string> = {
  critical: '紧急',
  review: '需审查',
  informative: '参考',
}

export const STANCE: Record<Stance, string> = {
  supports: '支持',
  challenges: '挑战',
  neutral: '中性',
  uncertain: '信息不足',
}

export const HEALTH: Record<string, string> = {
  active: '有效',
  corroborated: '已被支持',
  contested: '存在争议',
  revalidation_required: '需要重新验证',
}

export const ATTENTION: Record<string, string> = {
  stable: '稳定',
  new_support: '出现新的支持证据',
  needs_review: '需要审查',
  disputed: '存在争议 · 需要团队决策',
  competitor_pressure: '竞争压力',
  revalidation_required: '需要重新验证',
}

export const REVIEW_STATE: Record<ReviewState, string> = {
  candidate: '待确认',
  confirmed: '已确认',
  edited: '已修改确认',
  dismissed: '未采用',
  informative: '参考信息',
  rejected: '已拒绝',
  superseded: '已被新版本替代',
}

export const PRIORITY: Record<Priority, string> = {
  critical: '紧急',
  high: '高',
  medium: '中',
  low: '低',
}

export const COMPARABILITY: Record<Comparability, string> = {
  compatible: '可比',
  partial: '部分可比',
  incompatible: '不可比',
  unknown: '未知',
}

export const ACTION_STATUS: Record<ActionStatus, string> = {
  proposed: '待采用',
  open: '已采用 · 待开始',
  in_progress: '进行中',
  done: '已完成',
  dismissed: '已关闭',
}

export const SCAN_STATUS: Record<ScanStatus, string> = {
  pending: '排队中',
  running: '扫描中',
  cancel_requested: '取消中',
  completed: '已完成',
  failed: '失败',
  interrupted: '已中断',
  cancelled: '已取消',
}

export const IMPACT_MODE: Record<ImpactMode, string> = {
  replication: '独立复现',
  boundary_condition: '边界条件',
  method_substitution: '方法替代',
  prior_art: '在先工作',
  research_integrity: '研究完整性',
  no_material_change: '无材料性变化',
}

export const SUGGESTED_ACTION: Record<SuggestedAction, string> = {
  cite: '引用',
  add_boundary_discussion: '补边界讨论',
  run_comparison: '跑对比实验',
  narrow_claim: '收窄 Claim',
  team_review: '团队评审',
  revalidate: '重新验证',
  watch: '继续观察',
  no_action: '无需行动',
}

export const TRUST_STATE: Record<TrustState, string> = {
  generated: '已生成',
  grounded: '已定位',
  verified: '已核验',
  blocked: '未通过校验',
}

export const CONDITION_STATUS: Record<ConditionStatus, string> = {
  match: '一致',
  compatible_alias: '别名一致',
  partial: '部分一致',
  mismatch: '不一致',
  unknown: '未知',
}

export const CENTRALITY: Record<Centrality, string> = {
  core: '核心',
  major: '重要',
  minor: '次要',
}

export const EDIT_CLASS: Record<EditClass, string> = {
  add_citation: '补充引用',
  add_boundary_discussion: '补充边界讨论',
  add_limitation: '增加局限说明',
  qualify_claim: '收窄表述',
  experiment_todo: '实验待办',
}

export const APPROVAL_STATE: Record<ApprovalState, string> = {
  candidate: '待审批',
  approved: '已批准',
  rejected: '已拒绝',
}

export const VALIDATION_LABELS: Record<string, string> = {
  impact_confirmed: '影响已经人工采用',
  before_text_exact: '改写前文本可在当前文稿中精确定位',
  citations_resolved: '所有引用来源均已登记',
  citation_marker_safe: '未引入新的数字编号引用标记',
  locked_numbers_unchanged: '原文数字在改写后保持不变',
  original_file_untouched: '原论文文件未被修改',
}

export const CONTRACT_LABELS: Record<string, string> = {
  task: '任务',
  dataset: '数据集',
  split: '数据划分',
  metric: '指标',
  comparator: '对比基线',
  scope: '适用范围',
}

export const PUBLICATION_TYPE: Record<string, string> = {
  preprint: '预印本',
  journal_article: '已发表版本',
  conference_paper: '会议论文',
  other: '公开论文',
}

export const ACTION_TYPE: Record<ActionType, string> = {
  team_decision: '团队决策',
  experiment: '改实验',
  data: '补数据/条件',
  writing: '调整写作',
  cite: '引用/关注',
  competitor_response: '竞争响应',
  revalidation: '重新验证',
}

export const WATCH_ENTITY_TYPE: Record<string, string> = {
  lab: '实验室/团队',
  author: '作者',
  org: '机构',
}

// 徽章配色（spec §3）：critical 红；high 橙；medium 蓝；low 灰；
// supports/active/confirmed/edited 绿；challenges/revalidation_required 红；
// review/contested/candidate 橙；neutral/dismissed/rejected/superseded 灰；uncertain 黄；informative 蓝。
export function toneFor(key: string): Tone {
  const map: Record<string, Tone> = {
    critical: 'red',
    high: 'orange',
    medium: 'blue',
    low: 'gray',
    supports: 'green',
    active: 'green',
    confirmed: 'green',
    edited: 'green',
    challenges: 'red',
    revalidation_required: 'red',
    review: 'orange',
    contested: 'orange',
    candidate: 'orange',
    neutral: 'gray',
    dismissed: 'gray',
    rejected: 'gray',
    superseded: 'gray',
    uncertain: 'yellow',
    informative: 'blue',
    corroborated: 'green',
    // comparability
    compatible: 'green',
    partial: 'orange',
    incompatible: 'red',
    unknown: 'gray',
    // trust
    generated: 'gray',
    grounded: 'blue',
    verified: 'green',
    blocked: 'red',
    // action status
    proposed: 'orange',
    open: 'blue',
    in_progress: 'blue',
    done: 'green',
    // scan status
    pending: 'gray',
    running: 'blue',
    cancel_requested: 'orange',
    completed: 'green',
    failed: 'red',
    interrupted: 'orange',
    cancelled: 'gray',
    // condition status
    match: 'green',
    compatible_alias: 'green',
    mismatch: 'red',
    // centrality
    core: 'teal',
    major: 'blue',
    minor: 'gray',
    // approval
    approved: 'green',
    // attention
    stable: 'green',
    new_support: 'green',
    needs_review: 'orange',
    disputed: 'red',
    competitor_pressure: 'orange',
  }
  return map[key] ?? 'gray'
}

// 优先级/严重度色点颜色
export const DOT_COLOR: Record<Tone, string> = {
  red: '#ff3849',
  orange: '#ff9500',
  blue: '#1783ff',
  green: '#16c456',
  yellow: '#e3b400',
  gray: 'rgba(0,0,0,0.3)',
  teal: '#0E7490',
}
