import { useState } from 'react'
import { toast } from 'sonner'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import type { Impact, ImpactMode, SuggestedAction } from '@/types'
import { IMPACT_MODE, SUGGESTED_ACTION } from '@/lib/labels'
import { useAppStore } from '@/store/AppStore'
import { Button } from './Button'

const MODES = Object.keys(IMPACT_MODE) as ImpactMode[]
const ACTIONS = Object.keys(SUGGESTED_ACTION) as SuggestedAction[]

// 影响决策块（render_impact_decision，文献雷达与本周行动共用）
export function ImpactDecisionBlock({ impact }: { impact: Impact }) {
  const { impactState, decideImpact, confirm } = useAppStore()
  const review = impactState(impact)
  const [note, setNote] = useState('')
  const [open, setOpen] = useState(false)
  const [mode, setMode] = useState<ImpactMode>(impact.impact_mode)
  const [action, setAction] = useState<SuggestedAction>(impact.suggested_action)

  const adopted = review === 'confirmed' || review === 'edited'
  const dismissed = review === 'dismissed'
  const modified = mode !== impact.impact_mode || action !== impact.suggested_action

  const onAdopt = () => {
    if (impact.trust_state === 'blocked') {
      toast.error('这条影响的证据校验未通过，暂时不能采用；请先补齐原文证据。')
      return
    }
    decideImpact(impact, {
      review_state: modified ? 'edited' : 'confirmed',
      note: note.trim() || undefined,
      impact_mode: mode,
      suggested_action: action,
    })
    toast.success('已采用：影响进入证据账本，相关行动已打开')
  }

  const onDismiss = async () => {
    const ok = await confirm({
      actionName: '不采用这项影响',
      description: '不采用会关闭这项影响生成的相关行动；之后仍可重新采用。',
      confirmLabel: '确认不采用',
      danger: true,
    })
    if (!ok) return
    decideImpact(impact, { review_state: 'dismissed', note: note.trim() || undefined })
    toast.success('已记录不采用，并关闭相关行动')
  }

  return (
    <div className="rounded-[12px] border border-sep bg-white p-3">
      <Textarea
        value={note}
        onChange={(e) => setNote(e.target.value)}
        placeholder="决策备注（可选）"
        className="min-h-[68px] resize-y rounded-[10px] border-sep t-b2 focus-visible:ring-1 focus-visible:ring-kblue"
      />
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <Popover open={open} onOpenChange={setOpen}>
          <PopoverTrigger asChild>
            <Button variant="outline" size={26}>
              修改判断（可选）
            </Button>
          </PopoverTrigger>
          <PopoverContent align="start" className="w-72 rounded-[12px] border-sep p-3 shadow-[0_4px_16px_rgba(0,0,0,0.1)]">
            <div className="space-y-3">
              <div>
                <p className="mb-1 t-c1e text-ls">影响类型</p>
                <Select value={mode} onValueChange={(v) => setMode(v as ImpactMode)}>
                  <SelectTrigger className="h-8 rounded-[10px] border-sep t-b2">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {MODES.map((m) => (
                      <SelectItem key={m} value={m}>
                        {IMPACT_MODE[m]}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <p className="mb-1 t-c1e text-ls">建议动作</p>
                <Select value={action} onValueChange={(v) => setAction(v as SuggestedAction)}>
                  <SelectTrigger className="h-8 rounded-[10px] border-sep t-b2">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {ACTIONS.map((a) => (
                      <SelectItem key={a} value={a}>
                        {SUGGESTED_ACTION[a]}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <p className="t-c1 text-lt">不修改时“采用”会直接确认当前判断。</p>
            </div>
          </PopoverContent>
        </Popover>
        <div className="flex-1" />
        <Button variant="outline" size={32} disabled={dismissed} onClick={onDismiss}>
          不采用
        </Button>
        <Button size={32} disabled={adopted} onClick={onAdopt}>
          {impact.impact_mode === 'no_material_change' ? '确认无需行动' : '采用这项影响'}
        </Button>
      </div>
    </div>
  )
}
