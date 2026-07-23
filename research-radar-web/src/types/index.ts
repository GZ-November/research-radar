// TypeScript types matching src/data/seed.json (real export shape)

export interface ClaimContract {
  task?: string | null
  dataset?: string | null
  split?: string | null
  metric?: string | null
  comparator?: string | null
  scope?: string | null
}

export type Centrality = 'core' | 'major' | 'minor'
export type ReviewState =
  | 'candidate'
  | 'confirmed'
  | 'edited'
  | 'dismissed'
  | 'informative'
  | 'rejected'
  | 'superseded'

export interface ClaimRevision {
  id: string
  claim_id: string
  manuscript_version_id: string
  revision_no: number
  statement: string
  claim_type: string
  centrality: Centrality
  falsifiable_condition: string | null
  source_quote: string | null
  source_locator: string | null
  review_state: ReviewState
  supersedes_id: string | null
  created_at: string
  contract: ClaimContract
  is_current_version?: boolean
}

export interface Claim {
  id: string
  stable_key: string
  lifecycle_state: string
  revisions: ClaimRevision[]
}

export interface ManuscriptVersion {
  id: string
  version_no: number
  file_name: string
  source_type: string
  is_current: number
  created_at: string
}

export interface ScanStats {
  progress?: number
  scanned_papers?: number
  routed_pairs?: number
  impact_candidates?: number
  blocked_pairs?: number
  failed_pairs?: number
  search_queries?: string[]
  newest_publication?: string
  oldest_publication?: string
  full_text_papers?: number
  full_text_failures?: number
  integrity_checked?: number
  integrity_flagged?: number
  integrity_failures?: number
  crossref_enrich_failures?: number
  analysis_provider?: string
  analysis_model?: string
  embedding_provider?: string
  embedding_model?: string
  embedding_degraded?: boolean
  embedding_errors?: string[]
  [key: string]: unknown
}

export type ScanStatus =
  | 'pending'
  | 'running'
  | 'cancel_requested'
  | 'completed'
  | 'failed'
  | 'interrupted'
  | 'cancelled'

export interface Scan {
  id: string
  case_id: string
  mode?: string
  status: ScanStatus
  started_at: string | null
  finished_at: string | null
  error_message: string | null
  query?: { query?: string; queries?: string[]; [key: string]: unknown }
  stats: ScanStats
  created_at?: string
  updated_at?: string
}

export type Stance = 'supports' | 'challenges' | 'neutral' | 'uncertain'
export type ImpactMode =
  | 'replication'
  | 'boundary_condition'
  | 'method_substitution'
  | 'prior_art'
  | 'research_integrity'
  | 'no_material_change'
export type Comparability = 'compatible' | 'partial' | 'incompatible' | 'unknown'
export type Severity = 'critical' | 'review' | 'informative'
export type SuggestedAction =
  | 'cite'
  | 'add_boundary_discussion'
  | 'run_comparison'
  | 'narrow_claim'
  | 'team_review'
  | 'revalidate'
  | 'watch'
  | 'no_action'
export type TrustState = 'generated' | 'grounded' | 'verified' | 'blocked'
export type ConditionStatus = 'match' | 'compatible_alias' | 'partial' | 'mismatch' | 'unknown'

export interface ConditionDifference {
  field: string
  own_value: string | null
  incoming_value: string | null
  status: ConditionStatus
  explanation: string | null
}

export interface Evidence {
  quote: string | null
  locator: string | null
  source_snapshot_id?: string | null
}

export interface Source {
  id: string
  external_id?: string | null
  title: string
  authors: string[]
  published_at: string | null
  url: string | null
  doi: string | null
  arxiv_id?: string | null
  license?: string | null
  integrity_state?: string | null
  created_at?: string
  venue: string | null
  publication_type: string | null
  pdf_url: string | null
}

export interface Impact {
  id: string
  scan_run_id: string
  claim_revision_id: string | null
  source_snapshot_id: string | null
  event_type: string
  stance: Stance
  impact_mode: ImpactMode
  comparability: Comparability
  change_depth: number
  severity: Severity
  suggested_action: SuggestedAction
  review_state: ReviewState
  trust_state: TrustState
  created_at: string
  strategic_flags: string[]
  condition_differences: ConditionDifference[]
  evidence_own: Evidence | null
  evidence_new: Evidence | null
  uncertainty: string[]
  claim_stable_key: string
  claim_statement: string
  source: Source
  source_snapshot_abstract: string | null
}

export type ActionType =
  | 'team_decision'
  | 'experiment'
  | 'data'
  | 'writing'
  | 'cite'
  | 'competitor_response'
  | 'revalidation'
export type Priority = 'critical' | 'high' | 'medium' | 'low'
export type ActionStatus = 'proposed' | 'open' | 'in_progress' | 'done' | 'dismissed'

export interface RadarAction {
  id: string
  case_id: string
  scan_run_id: string | null
  impact_candidate_id: string | null
  claim_revision_id: string | null
  action_type: ActionType
  priority: Priority
  title: string
  rationale: string
  due_label: string | null
  status: ActionStatus
  created_at: string
  advice_source: string | null
  checklist: string[]
  source_title: string | null
  source_url: string | null
}

export type EditClass =
  | 'add_citation'
  | 'add_boundary_discussion'
  | 'add_limitation'
  | 'qualify_claim'
  | 'experiment_todo'
export type ApprovalState = 'candidate' | 'approved' | 'rejected'

export interface PatchValidations {
  impact_confirmed: boolean
  before_text_exact: boolean
  citations_resolved: boolean
  citation_marker_safe: boolean
  locked_numbers_unchanged: boolean
  original_file_untouched: boolean
}

export interface Patch {
  id: string
  case_id: string
  manuscript_version_id: string
  impact_candidate_id: string | null
  target_locator: string
  edit_class: EditClass
  before_text: string
  after_text: string
  created_at: string
  citations: string[]
  evidence_refs?: Evidence[]
  validations: PatchValidations
  approval_state: ApprovalState
}

export interface WatchEntity {
  id: string
  case_id: string
  entity_type: 'lab' | 'author' | 'org'
  canonical_name: string
  created_at: string
  aliases: string[]
}

export interface ClaimProfile {
  stable_key: string
  role: string
  claim_summary: string
  contract: ClaimContract
  boundary_conditions: string[]
  falsification_tests?: string[]
}

export interface ProfileOutput {
  title: string
  research_problem: string | null
  central_thesis: string | null
  contributions: string[]
  key_findings: string[]
  limitations: string[]
  watch_topics: string[]
  claim_profiles: ClaimProfile[]
  datasets?: string[]
  methods?: string[]
  [key: string]: unknown
}

export interface Profile {
  output: ProfileOutput
  model: string
  created_at: string
}

export interface ModelRun {
  stage: string
  provider: string
  model: string
  latency_ms: number
  estimated_cost: number
  created_at: string
  validation: Record<string, unknown> | null
}

export interface AuditEvent {
  event_type: string
  object_type: string
  object_id: string
  actor_type: string
  created_at: string
  payload: Record<string, unknown> | null
}

export interface CaseSettings {
  fixture_version?: string
  language?: string
  fixture_dir?: string
  is_sample?: boolean
  generated_search_queries?: { question_hash?: string; queries: string[] }
}

export interface Case {
  id: string
  title: string
  research_question: string
  is_demo: boolean
  settings: CaseSettings
  created_at: string
  versions: ManuscriptVersion[]
  claims: Claim[]
  scans: Scan[]
  latest_scan_id: string | null
  impacts: Impact[]
  actions: RadarAction[]
  patches: Patch[]
  watch_entities: WatchEntity[]
  profile: Profile | null
  model_runs: ModelRun[]
  audit_events: AuditEvent[]
  review_decisions: unknown[]
}

export interface Seed {
  cases: Case[]
}
