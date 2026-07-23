import { useMemo, useState } from 'react';
import { getSettings, putSettings, testSettings, useApi, type SettingsData } from '../api';
import { Reveal } from '../components/chrome';
import { Spinner } from '../components/ui/spinner';

type RemoteProvider = 'deepseek' | 'openai' | 'custom';
type SaveState = 'idle' | 'saving' | 'ok' | 'warning' | 'error';

const PROVIDERS: Record<
  RemoteProvider,
  { label: string; baseUrl: string; defaultModel: string; help: string }
> = {
  deepseek: {
    label: 'DeepSeek',
    baseUrl: 'https://api.deepseek.com',
    defaultModel: 'deepseek-v4-flash',
    help: 'V4 Flash 适合默认扫描；复杂、质量优先的研究判断可选 V4 Pro。',
  },
  openai: {
    label: 'OpenAI',
    baseUrl: 'https://api.openai.com/v1',
    defaultModel: 'gpt-5.6-terra',
    help: 'Terra 平衡质量与成本；Sol 用于最复杂分析；Luna 适合高频轻量任务。',
  },
  custom: {
    label: '兼容接口',
    baseUrl: '',
    defaultModel: '',
    help: '适用于支持 OpenAI Chat Completions 与结构化输出的兼容服务。',
  },
};

function providerFrom(settings: SettingsData): RemoteProvider {
  const provider = settings.llm.provider.toLowerCase();
  const base = settings.llm.base_url.toLowerCase();
  if (provider === 'deepseek' || base.includes('deepseek')) return 'deepseek';
  if (provider === 'openai' || base.includes('openai.com')) return 'openai';
  return 'custom';
}

export default function Settings() {
  const { data, loading, error, refetch } = useApi<SettingsData>(() => getSettings(), []);

  if (loading && !data) {
    return (
      <div className="flex items-center justify-center py-20">
        <Spinner className="size-8 text-neutral-400" />
      </div>
    );
  }
  if (error || !data) {
    return (
      <div className="card p-8 text-center text-sm text-red-600">
        设置加载失败：{error?.message ?? '未知错误'}
      </div>
    );
  }

  // Keep the form instance mounted while refetching after a save so the
  // connection-test result is not immediately erased by a key-driven remount.
  return <SettingsForm initial={data} onSaved={refetch} />;
}

function SettingsForm({ initial, onSaved }: { initial: SettingsData; onSaved: () => void }) {
  const initialProvider = providerFrom(initial);
  const [mode, setMode] = useState<'remote' | 'local'>(
    initial.llm.mode === 'local' ? 'local' : 'remote',
  );
  const [provider, setProvider] = useState<RemoteProvider>(initialProvider);
  const [baseUrl, setBaseUrl] = useState(
    initial.llm.mode === 'remote' && initial.llm.base_url
      ? initial.llm.base_url
      : PROVIDERS[initialProvider].baseUrl,
  );
  const [model, setModel] = useState(
    initial.llm.mode === 'remote' && initial.llm.model
      ? initial.llm.model
      : PROVIDERS[initialProvider].defaultModel,
  );
  const [apiKey, setApiKey] = useState('');
  const [thinking, setThinking] = useState(initial.llm.thinking);
  const [reasoningEffort, setReasoningEffort] = useState(initial.llm.reasoning_effort);
  const [localModel, setLocalModel] = useState(initial.local_llm.model);
  const [localBaseUrl, setLocalBaseUrl] = useState(initial.local_llm.base_url);

  const [embeddingEnabled, setEmbeddingEnabled] = useState(initial.embedding.configured);
  const [embeddingProvider, setEmbeddingProvider] = useState(
    initial.embedding.provider || 'openai',
  );
  const [embeddingBaseUrl, setEmbeddingBaseUrl] = useState(
    initial.embedding.base_url || 'https://api.openai.com/v1',
  );
  const [embeddingModel, setEmbeddingModel] = useState(
    initial.embedding.model || 'text-embedding-3-small',
  );
  const [embeddingApiKey, setEmbeddingApiKey] = useState('');

  const [saveState, setSaveState] = useState<SaveState>('idle');
  const [message, setMessage] = useState('');

  const suggestions = useMemo(
    () => initial.model_catalog[provider] ?? [],
    [initial.model_catalog, provider],
  );
  const effortOptions =
    provider === 'deepseek'
      ? ['high', 'max']
      : ['none', 'low', 'medium', 'high', 'xhigh', 'max'];

  const changeProvider = (next: RemoteProvider) => {
    setProvider(next);
    setBaseUrl(PROVIDERS[next].baseUrl);
    setModel(PROVIDERS[next].defaultModel);
    if (next === 'deepseek' && !['high', 'max'].includes(reasoningEffort)) {
      setReasoningEffort('high');
    }
  };

  const save = async () => {
    setSaveState('saving');
    setMessage('');

    const updates: Record<string, string> = {};
    if (mode === 'local') {
      if (!localModel.trim() || !localBaseUrl.trim()) {
        setSaveState('error');
        setMessage('请填写 Ollama 模型名和服务地址。');
        return;
      }
      updates.LOCAL_LLM_MODEL = localModel.trim();
      updates.LOCAL_LLM_BASE_URL = localBaseUrl.trim();
    } else {
      if (!model.trim() || !baseUrl.trim()) {
        setSaveState('error');
        setMessage('请填写模型名和接口地址。');
        return;
      }
      updates.LOCAL_LLM_MODEL = '';
      updates.LLM_PROVIDER = provider === 'custom' ? 'openai_compatible' : provider;
      updates.LLM_BASE_URL = baseUrl.trim();
      updates.LLM_MODEL = model.trim();
      updates.LLM_THINKING = thinking;
      updates.LLM_REASONING_EFFORT = reasoningEffort;
      if (apiKey.trim()) updates.LLM_API_KEY = apiKey.trim();
    }

    if (embeddingEnabled) {
      if (!embeddingProvider.trim() || !embeddingModel.trim() || !embeddingBaseUrl.trim()) {
        setSaveState('error');
        setMessage('向量检索已开启，请完整填写 provider、模型和接口地址。');
        return;
      }
      updates.EMBEDDING_PROVIDER = embeddingProvider.trim();
      updates.EMBEDDING_MODEL = embeddingModel.trim();
      updates.EMBEDDING_BASE_URL = embeddingBaseUrl.trim();
      if (embeddingApiKey.trim()) updates.EMBEDDING_API_KEY = embeddingApiKey.trim();
    } else {
      updates.EMBEDDING_PROVIDER = '';
      updates.EMBEDDING_MODEL = '';
      updates.EMBEDDING_BASE_URL = '';
    }

    try {
      await putSettings(updates);
      setApiKey('');
      setEmbeddingApiKey('');
      try {
        const result = await testSettings();
        setSaveState('ok');
        setMessage(`已保存并连接成功：${result.provider} · ${result.model}`);
      } catch (e) {
        setSaveState('warning');
        setMessage(`设置已保存，但连接检查未通过：${e instanceof Error ? e.message : String(e)}`);
      }
      onSaved();
    } catch (e) {
      setSaveState('error');
      setMessage(e instanceof Error ? e.message : String(e));
    }
  };

  return (
    <div className="max-w-2xl">
      <Reveal>
        <div className="kicker mb-2">Settings</div>
        <h1 className="display-lg mb-3">模型设置</h1>
        <p className="text-sm text-neutral-500 mb-10 leading-relaxed">
          分析模型负责 Claim 提取、文献比较与行动建议；向量模型只负责语义检索，两者独立配置。
        </p>
      </Reveal>

      <Reveal delay={50}>
        <section className="card p-7 grid gap-6">
          <div>
            <div className="text-xs text-neutral-500 tracking-wide mb-2">运行方式</div>
            <div className="flex gap-2">
              {([
                ['remote', '远程 API'],
                ['local', '本地 Ollama'],
              ] as const).map(([value, label]) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => setMode(value)}
                  className={`px-4 py-2.5 rounded-lg text-sm border transition-colors ${
                    mode === value
                      ? 'border-teal bg-teal-soft text-teal'
                      : 'border-hairline text-neutral-500 hover:border-neutral-300'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          {mode === 'remote' ? (
            <>
              <div>
                <div className="text-xs text-neutral-500 tracking-wide mb-2">提供商</div>
                <div className="flex flex-wrap gap-2">
                  {(Object.keys(PROVIDERS) as RemoteProvider[]).map((key) => (
                    <button
                      key={key}
                      type="button"
                      onClick={() => changeProvider(key)}
                      className={`px-4 py-2.5 rounded-lg text-sm border transition-colors ${
                        provider === key
                          ? 'border-teal bg-teal-soft text-teal'
                          : 'border-hairline text-neutral-500 hover:border-neutral-300'
                      }`}
                    >
                      {PROVIDERS[key].label}
                    </button>
                  ))}
                </div>
                <p className="mt-2 text-xs text-neutral-400">{PROVIDERS[provider].help}</p>
              </div>

              <label>
                <span className="text-xs text-neutral-500">模型</span>
                <input
                  className="input mt-1.5 font-mono !text-[12px]"
                  list="analysis-models"
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                  placeholder="输入服务实际提供的模型 ID"
                />
                <datalist id="analysis-models">
                  {suggestions.map((item) => (
                    <option key={item.id} value={item.id}>{item.label}</option>
                  ))}
                </datalist>
                <span className="mt-1 block text-[11px] text-neutral-400">
                  可直接输入自定义模型 ID，不会被下拉列表限制。
                </span>
              </label>

              <label>
                <span className="text-xs text-neutral-500">接口地址</span>
                <input
                  className="input mt-1.5 font-mono !text-[12px]"
                  value={baseUrl}
                  onChange={(e) => setBaseUrl(e.target.value)}
                  placeholder="https://api.example.com/v1"
                />
              </label>

              <label>
                <span className="text-xs text-neutral-500">API Key</span>
                <input
                  className="input mt-1.5 font-mono !text-[12px]"
                  type="password"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder={initial.llm.has_api_key ? '已保存 · 留空保持不变' : 'sk-…'}
                />
              </label>

              <div className="grid sm:grid-cols-2 gap-4">
                <label>
                  <span className="text-xs text-neutral-500">思考模式</span>
                  <select
                    className="input mt-1.5"
                    value={thinking}
                    onChange={(e) => setThinking(e.target.value as 'enabled' | 'disabled')}
                  >
                    <option value="enabled">开启</option>
                    <option value="disabled">关闭</option>
                  </select>
                </label>
                <label>
                  <span className="text-xs text-neutral-500">推理强度</span>
                  <select
                    className="input mt-1.5"
                    value={reasoningEffort}
                    onChange={(e) => setReasoningEffort(e.target.value as SettingsData['llm']['reasoning_effort'])}
                  >
                    {effortOptions.map((effort) => (
                      <option key={effort} value={effort}>{effort}</option>
                    ))}
                  </select>
                </label>
              </div>
            </>
          ) : (
            <>
              <label>
                <span className="text-xs text-neutral-500">Ollama 模型名</span>
                <input
                  className="input mt-1.5 font-mono !text-[12px]"
                  value={localModel}
                  onChange={(e) => setLocalModel(e.target.value)}
                  placeholder="qwen3:8b"
                />
              </label>
              <label>
                <span className="text-xs text-neutral-500">Ollama 地址</span>
                <input
                  className="input mt-1.5 font-mono !text-[12px]"
                  value={localBaseUrl}
                  onChange={(e) => setLocalBaseUrl(e.target.value)}
                  placeholder="http://127.0.0.1:11434"
                />
                <span className="mt-1 block text-[11px] text-neutral-400">
                  Docker Desktop 中访问宿主机 Ollama 时使用 http://host.docker.internal:11434
                </span>
              </label>
            </>
          )}
        </section>
      </Reveal>

      <Reveal delay={90}>
        <section className="card p-7 mt-6 grid gap-5">
          <div className="flex items-center justify-between gap-4">
            <div>
              <h2 className="font-serif font-semibold text-lg">向量检索</h2>
              <p className="text-xs text-neutral-400 mt-1">可选；关闭时自动退化为关键词检索。</p>
            </div>
            <button
              type="button"
              className={`chip ${embeddingEnabled ? '!border-teal !text-teal !bg-teal-soft' : ''}`}
              onClick={() => setEmbeddingEnabled((value) => !value)}
            >
              {embeddingEnabled ? '已开启' : '已关闭'}
            </button>
          </div>
          {embeddingEnabled && (
            <>
              <div className="grid sm:grid-cols-2 gap-4">
                <label>
                  <span className="text-xs text-neutral-500">Provider</span>
                  <select
                    className="input mt-1.5"
                    value={embeddingProvider}
                    onChange={(e) => {
                      const value = e.target.value;
                      setEmbeddingProvider(value);
                      if (value === 'ollama') {
                        setEmbeddingBaseUrl('http://127.0.0.1:11434');
                        setEmbeddingModel('qwen3-embedding:0.6b');
                      } else if (value === 'openai') {
                        setEmbeddingBaseUrl('https://api.openai.com/v1');
                        setEmbeddingModel('text-embedding-3-small');
                      }
                    }}
                  >
                    <option value="openai">OpenAI</option>
                    <option value="ollama">本地 Ollama</option>
                    <option value="openai_compatible">兼容接口</option>
                  </select>
                </label>
                <label>
                  <span className="text-xs text-neutral-500">向量模型</span>
                  <input
                    className="input mt-1.5 font-mono !text-[12px]"
                    value={embeddingModel}
                    onChange={(e) => setEmbeddingModel(e.target.value)}
                  />
                </label>
              </div>
              <label>
                <span className="text-xs text-neutral-500">向量接口地址</span>
                <input
                  className="input mt-1.5 font-mono !text-[12px]"
                  value={embeddingBaseUrl}
                  onChange={(e) => setEmbeddingBaseUrl(e.target.value)}
                />
              </label>
              {embeddingProvider !== 'ollama' && (
                <label>
                  <span className="text-xs text-neutral-500">向量 API Key</span>
                  <input
                    className="input mt-1.5 font-mono !text-[12px]"
                    type="password"
                    value={embeddingApiKey}
                    onChange={(e) => setEmbeddingApiKey(e.target.value)}
                    placeholder={initial.embedding.has_api_key ? '已保存 · 留空保持不变' : 'sk-…'}
                  />
                </label>
              )}
            </>
          )}
        </section>
      </Reveal>

      <Reveal delay={120}>
        <div className="mt-6 flex flex-wrap items-center gap-3">
          <button className="btn-dark" onClick={() => void save()} disabled={saveState === 'saving'}>
            {saveState === 'saving' ? '保存并检测中…' : '保存并检测连接'}
          </button>
          {message && (
            <span
              className={`text-xs ${
                saveState === 'ok'
                  ? 'text-green-700'
                  : saveState === 'warning'
                    ? 'text-amber-700'
                    : 'text-red-700'
              }`}
            >
              {message}
            </span>
          )}
        </div>
      </Reveal>
    </div>
  );
}
