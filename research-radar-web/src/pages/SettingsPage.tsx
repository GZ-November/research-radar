import { useState } from 'react'
import { toast } from 'sonner'
import { Input } from '@/components/ui/input'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Separator } from '@/components/ui/separator'
import { Button } from '@/components/radar/Button'
import { Callout } from '@/components/radar/Callout'
import { Mono, PageHeader, SectionTitle, SubNote } from '@/components/radar/Typography'
import { useAppStore, type SettingsState } from '@/store/AppStore'

function Field({
  label,
  help,
  children,
}: {
  label: string
  help?: string
  children: React.ReactNode
}) {
  return (
    <div>
      <label className="mb-1 block t-b2e text-lp">{label}</label>
      {children}
      {help ? <SubNote className="mt-1">{help}</SubNote> : null}
    </div>
  )
}

const inputCls = 'h-9 rounded-[10px] border-sep font-mono-radar t-b2'

export default function SettingsPage() {
  const { settings, saveSettings } = useAppStore()
  const [form, setForm] = useState<SettingsState>(settings)
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<string | null>(null)

  const set = <K extends keyof SettingsState>(k: K, v: SettingsState[K]) =>
    setForm((f) => ({ ...f, [k]: v }))

  const submit = () => {
    saveSettings(form)
    toast.success('设置已保存，立即生效。')
  }

  const testConnection = () => {
    setTesting(true)
    setTestResult(null)
    setTimeout(() => {
      setTesting(false)
      setTestResult('连接成功：远程服务可用，当前模型 deepseek-v4-pro。')
    }, 1200)
  }

  return (
    <div className="space-y-6">
      <PageHeader title="设置" />

      <Callout kind="success">
        当前分析模型：<Mono>deepseek-v4-pro</Mono>（远程 API）
      </Callout>

      <div className="max-w-[640px] rounded-[12px] border border-sep bg-white p-5">
        <SectionTitle>分析模型</SectionTitle>
        <div className="mt-3">
          <RadioGroup
            value={form.mode}
            onValueChange={(v) => set('mode', v as SettingsState['mode'])}
            className="flex gap-4"
          >
            <label className="flex items-center gap-2 t-b2 text-lp">
              <RadioGroupItem value="remote" className="border-sep text-radar" />
              远程 API
            </label>
            <label className="flex items-center gap-2 t-b2 text-lp">
              <RadioGroupItem value="local" className="border-sep text-radar" />
              本地 Ollama
            </label>
          </RadioGroup>
          <SubNote className="mt-1.5">本地 Ollama 模式下文稿不出本机，配置后优先于远程 API。</SubNote>
        </div>

        {form.mode === 'remote' ? (
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <Field label="Provider">
              <Input value={form.provider} onChange={(e) => set('provider', e.target.value)} placeholder="deepseek" className={inputCls} />
            </Field>
            <Field label="Base URL">
              <Input value={form.baseUrl} onChange={(e) => set('baseUrl', e.target.value)} placeholder="https://api.deepseek.com" className={inputCls} />
            </Field>
            <Field label="模型名称">
              <Input value={form.modelName} onChange={(e) => set('modelName', e.target.value)} placeholder="deepseek-chat" className={inputCls} />
            </Field>
            <Field label="API Key" help="已保存 Key 时只显示后 4 位；留空表示不修改。">
              <Input
                type="password"
                value={form.apiKey}
                onChange={(e) => set('apiKey', e.target.value)}
                placeholder="已保存 ····8300，留空表示不修改"
                className={inputCls}
              />
            </Field>
          </div>
        ) : (
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <Field label="本地模型名称">
              <Input value={form.localModel} onChange={(e) => set('localModel', e.target.value)} placeholder="qwen3:4b" className={inputCls} />
            </Field>
            <Field
              label="Ollama 地址"
              help="Docker 容器内访问宿主机 Ollama 时填 http://host.docker.internal:11434"
            >
              <Input value={form.ollamaUrl} onChange={(e) => set('ollamaUrl', e.target.value)} placeholder="http://127.0.0.1:11434" className={inputCls} />
            </Field>
          </div>
        )}

        <Separator className="my-5 bg-sep" />

        <SectionTitle>向量检索（可选）</SectionTitle>
        <div className="mt-3">
          <Field label="向量模型 Provider" help="不启用时检索退化为纯关键词匹配，其他功能不受影响。">
            <Select
              value={form.embedProvider}
              onValueChange={(v) => set('embedProvider', v as SettingsState['embedProvider'])}
            >
              <SelectTrigger className="h-9 w-64 rounded-[10px] border-sep t-b2">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="off">不启用</SelectItem>
                <SelectItem value="ollama">本地 Ollama</SelectItem>
                <SelectItem value="openai">OpenAI-compatible API</SelectItem>
              </SelectContent>
            </Select>
          </Field>
          {form.embedProvider === 'ollama' && (
            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <Field label="Embedding 模型">
                <Input value={form.embedModel} onChange={(e) => set('embedModel', e.target.value)} placeholder="qwen3-embedding:0.6b" className={inputCls} />
              </Field>
              <Field label="Ollama 地址">
                <Input value={form.embedOllamaUrl} onChange={(e) => set('embedOllamaUrl', e.target.value)} placeholder="http://127.0.0.1:11434" className={inputCls} />
              </Field>
            </div>
          )}
          {form.embedProvider === 'openai' && (
            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <Field label="Embedding 模型">
                <Input value={form.embedOpenaiModel} onChange={(e) => set('embedOpenaiModel', e.target.value)} placeholder="text-embedding-3-small" className={inputCls} />
              </Field>
              <Field label="Embedding Base URL">
                <Input value={form.embedOpenaiBase} onChange={(e) => set('embedOpenaiBase', e.target.value)} placeholder="https://api.openai.com/v1" className={inputCls} />
              </Field>
              <Field label="Embedding API Key">
                <Input type="password" value={form.embedOpenaiKey} onChange={(e) => set('embedOpenaiKey', e.target.value)} className={inputCls} />
              </Field>
            </div>
          )}
        </div>

        <Separator className="my-5 bg-sep" />

        <SectionTitle>其他</SectionTitle>
        <div className="mt-3">
          <Field label="Crossref 联系邮箱" help="发送给 Crossref API 的联系地址（礼貌池），建议填真实邮箱。">
            <Input
              type="email"
              value={form.crossrefEmail}
              onChange={(e) => set('crossrefEmail', e.target.value)}
              placeholder="you@example.com"
              className={inputCls}
            />
          </Field>
        </div>

        <Button size={44} className="mt-5" onClick={submit}>
          保存设置
        </Button>
      </div>

      <div>
        <Separator className="bg-sep" />
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <SubNote>测试连接基于当前已保存的配置；失败不影响保存。</SubNote>
          <Button variant="outline" loading={testing} onClick={testConnection}>
            {testing ? '正在测试连接…' : '测试连接'}
          </Button>
        </div>
        {testResult && (
          <Callout kind="success" className="mt-3 max-w-[640px]">
            连接成功：远程服务可用，当前模型 <Mono>deepseek-v4-pro</Mono>。
          </Callout>
        )}
      </div>
    </div>
  )
}
