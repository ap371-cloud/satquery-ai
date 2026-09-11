import React, { useEffect, useMemo, useRef, useState } from 'react'
import {
  Activity, AlertTriangle, Check, CheckCircle2, ChevronDown, Copy, Database,
  Download, FileJson, Image as ImageIcon, Layers3, LoaderCircle, Map as MapIcon, Orbit,
  Play, Plus, Radio, RotateCcw, Satellite, Settings2, Sparkles, Terminal,
  Upload, X, Zap, CloudDownload, Cpu, ShieldCheck, Gauge, Lightbulb
} from 'lucide-react'
import { api, apiUrl, uploadDataset } from './api.js'
import GeoEvidenceMap from './GeoEvidenceMap.jsx'

const EXAMPLES = [
  {
    title: 'Assam flood — auto retrieval',
    query: 'Show flooded areas around Assam between July and August 2025.',
    hint: 'No upload required',
  },
  {
    title: 'Urban expansion',
    query: 'Show where urban construction changed between these two dates.',
    hint: '2 optical images',
  },
  {
    title: 'Vegetation loss',
    query: 'Where was vegetation lost between these two images?',
    hint: '2 optical images',
  },
  {
    title: 'Vision assistant',
    query: 'Describe the major land-cover patterns visible in this image.',
    hint: '1 image · VLM when connected',
  },
  {
    title: 'Ground buildings',
    query: 'Highlight all buildings in this image.',
    hint: '1 optical image · text segmentation',
  },
  {
    title: 'Temporal visual Q&A',
    query: 'What are the most important visible differences between these two satellite images?',
    hint: '2 images · temporal VLM',
  },
  {
    title: 'Optical + SAR joint analysis',
    query: 'Use both optical and SAR images for joint analysis',
    hint: '1 optical + 1 SAR · multimodal specialist',
  },
]

const STAGE_LABELS = {
  queued: 'Queued',
  validating_input: 'Understanding request',
  planning: 'Planning workflow',
  preprocessing: 'Preparing imagery',
  running_models: 'Running specialist tools',
  geo_processing: 'Geospatial processing',
  validating_evidence: 'Validating evidence',
  generating_response: 'Generating answer',
  completed: 'Completed',
  failed: 'Failed',
}

function formatDate(value) {
  if (!value) return ''
  try { return new Date(value).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) }
  catch { return '' }
}

function formatMeta(dataset) {
  if (!dataset) return []
  const m = dataset.metadata || {}
  return [
    dataset.modality ? dataset.modality.toUpperCase() : null,
    m.acquired_at || m.period_label || null,
    m.crs || 'No CRS',
    m.resolution ? `${Number(m.resolution[0]).toFixed(m.resolution[0] < 1 ? 5 : 1)} × ${Number(m.resolution[1]).toFixed(m.resolution[1] < 1 ? 5 : 1)}` : null,
    m.width && m.height ? `${m.width}×${m.height}` : null,
  ].filter(Boolean)
}

function visionStatusText(health) {
  const va = health?.specialists?.vision_assistant
  if (!va) return 'checking'
  if (va.ready && va.model_name) return `${va.model_name} · model-backed`
  if (va.ready) return 'model-backed ready'
  if (va.reachable) return `${va.model_loaded ? 'model loaded' : 'starting service'}`
  return 'VLM offline · semantic fallback'
}

function Brand() {
  return (
    <div className="brand-wrap hero-wrap-float">
      <div className="brand-logo" aria-label="SatQuery AI">
        <div className="brand-orbit"><Orbit size={58} strokeWidth={1.65}/></div>
        <div className="brand-word"><span>SatQuery</span><b>AI</b></div>
      </div>
      <div className="brand-extension"><span>Agentic Multimodal Earth Intelligence</span></div>
      <h2>Ask Earth. AI Plans. Models Analyze. Evidence Answers.</h2>
      <h1>Live Analysis <span>Workspace</span></h1>
      <div className="hero-chips">
        <span className="hero-chip"><Sparkles size={14}/><b>Sensor-aware routing</b></span>
        <span className="hero-chip"><Layers3 size={14}/><b>Evidence-first answers</b></span>
        <span className="hero-chip"><Satellite size={14}/><b>Optical + SAR fusion</b></span>
      </div>
    </div>
  )
}

function StatusBadge({ health }) {
  const ready = health?.status === 'ok'
  return (
    <div className="runtime-health" title="SatQuery backend health">
      <span className={`health-dot ${ready ? 'online' : 'fallback'}`}/>
      <span>{ready ? 'SatQuery runtime ready' : 'Checking runtime'}</span>
    </div>
  )
}

function QueryContext({ context }) {
  if (!context) return null
  const loc = context.location?.name
  const dr = context.date_range
  return (
    <div className="query-context">
      {loc && <span><MapIcon size={12}/>{loc}</span>}
      {dr && <span><Activity size={12}/>{dr.start_date} → {dr.end_date}</span>}
      {context.preferred_sensor && <span><Satellite size={12}/>{context.preferred_sensor.toUpperCase()}</span>}
      {context.unresolved_location_text && !loc && <span><MapIcon size={12}/>Resolve: {context.unresolved_location_text}</span>}
      {context.target_object && <span><Sparkles size={12}/>Target: {context.target_object}</span>}
      {context.vision_assistant && <span><Cpu size={12}/>Vision assistant route</span>}
      {context.multimodal && <span><Layers3 size={12}/>Optical + SAR joint route</span>}
      {context.can_auto_retrieve && <span className="auto-chip"><CloudDownload size={12}/>Auto satellite retrieval ready</span>}
      {context.supported === false && <span className="unsupported-chip"><AlertTriangle size={12}/>Unsupported in current build</span>}
    </div>
  )
}

function yearOf(dataset) {
  if (!dataset) return null
  const m = dataset.metadata || {}
  const fromMeta = (m.acquired_at || '').match(/(20\d\d)/) || (m.period_label || '').match(/(20\d\d)/)
  if (fromMeta) return fromMeta[1]
  const fromName = (dataset.filename || '').match(/(20\d\d)/)
  return fromName ? fromName[1] : null
}

function suggestFor(primary, compare, dataset) {
  if (!primary) return []
  const pM = primary.modality || ''
  const cM = compare?.modality || ''
  const py = yearOf(primary)
  const cy = yearOf(compare)
  const isAssam = /(assam|guwahati|brahmaputra)/i.test(`${primary.filename || ''} ${compare?.filename || ''}`)
  const isIndore = /indore/i.test(`${primary.filename || ''} ${compare?.filename || ''}`)
  const hasPlace = isAssam ? 'Assam' : isIndore ? 'Indore' : ''
  const items = []
  const push = (label, query) => {
    if (query) items.push({ label, query })
  }
  if (pM === 'sar' && cM === 'sar') {
    const place = hasPlace ? `around ${hasPlace}` : 'in this area'
    push('Flood / water compare', `Show flooded areas ${place} and highlight what changed between these two SAR scenes.`)
    push('Radar change detection', 'What changed between these two SAR images? Highlight significant radar differences.')
    push('Water presence', 'Is there standing water or flooding visible in the earlier SAR image?')
  } else if (pM === 'optical' && cM === 'optical' && py && cy && py !== cy) {
    push('Urban growth', 'Show where urban construction changed between these two dates.')
    push('Vegetation loss', 'Where was vegetation lost between these two images?')
    push('Temporal visual', 'What are the most important visible differences between these two satellite images?')
  } else if (pM === 'optical' && cM === 'optical') {
    push('Land cover', 'Describe the major land-cover patterns visible in this image.')
    push('Buildings', 'Highlight all buildings in this image.')
    push('Water check', 'Is there any visible water or flooding in this image?')
  } else if ((pM === 'optical' && cM === 'sar') || (pM === 'sar' && cM === 'optical')) {
    push('Optical + SAR fusion', 'Use both optical and SAR images for joint analysis.')
    push('Flood cross-check', 'Has flooding occurred here? Compare the optical and SAR evidence.')
  } else if (pM === 'sar') {
    push('Water / flood in SAR', 'Is there standing water or flooding visible in this SAR image?')
    push('Backscatter read', 'Describe the radar backscatter patterns and what they suggest about land cover.')
    push('Bright returns', 'Highlight bright radar returns, which often indicate settlements, buildings or disturbed ground.')
  } else {
    push('Land cover', 'Describe the major land-cover patterns visible in this image.')
    push('Buildings', 'Highlight all buildings in this image.')
    push('Water check', 'Is there any visible water or flooding in this image?')
    push('Recent changes', 'Identify any recent changes or anomalies visible in this scene.')
  }
  const seen = new Set()
  return items.filter(it => {
    if (seen.has(it.query)) return false
    seen.add(it.query)
    return true
  }).slice(0, 4)
}

function ImageSuggestions({ primary, compare, run, setQuery }) {
  const items = useMemo(() => suggestFor(primary, compare), [primary, compare])
  if (!primary || items.length === 0) return null
  return (
    <div className="suggestion-box">
      <div className="suggestion-title"><Lightbulb size={13}/> Auto-guessed from your imagery</div>
      <div className="suggestion-chips">
        {items.map(it => (
          <button className="suggestion-chip" key={it.query} onClick={() => { setQuery(it.query); run(it.query) }}>
            <span>{it.label}</span>
            <small>{it.query}</small>
          </button>
        ))}
      </div>
    </div>
  )
}

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, message: '' }
  }
  static getDerivedStateFromError(error) {
    return { hasError: true, message: String((error && error.message) || error || 'Unknown error') }
  }
  componentDidCatch(error, info) {
    console.error('SatQuery render error:', error, info)
  }
  handleReset() {
    this.setState({ hasError: false, message: '' })
  }
  render() {
    if (this.state.hasError) {
      return (
        <div className="crash-card">
          <AlertTriangle size={22}/>
          <div>
            <b>Something went wrong on-screen</b>
            <span>{this.state.message}</span>
          </div>
          <button onClick={this.handleReset.bind(this)}>Try again</button>
          <button onClick={() => window.location.reload()}>Reload</button>
        </div>
      )
    }
    return this.props.children
  }
}

function App() {
  const [datasets, setDatasets] = useState([])
  const [primaryId, setPrimaryId] = useState(null)
  const [compareId, setCompareId] = useState(null)
  const [query, setQuery] = useState('')
  const [queryContext, setQueryContext] = useState(null)
  const [provider, setProvider] = useState('auto')
  const [analysisId, setAnalysisId] = useState(null)
  const [status, setStatus] = useState(null)
  const [result, setResult] = useState(null)
  const [health, setHealth] = useState(null)
  const [history, setHistory] = useState([])
  const [busyUpload, setBusyUpload] = useState(null)
  const [error, setError] = useState('')
  const [advancedOpen, setAdvancedOpen] = useState(false)
  const [libraryOpen, setLibraryOpen] = useState(false)
  const [askedQuestion, setAskedQuestion] = useState('')
  const runSeq = useRef(0)

  const selectedIds = useMemo(() => [primaryId, compareId].filter(Boolean), [primaryId, compareId])
  const primary = datasets.find(d => d.id === primaryId) || null
  const compare = datasets.find(d => d.id === compareId) || null
  const running = status && !['completed', 'failed'].includes(status.status)
  const canRunWithoutUpload = Boolean(queryContext?.can_auto_retrieve)

  async function refresh(quiet) {
    try {
      const [ds, he, hi] = await Promise.all([
        api('/api/v1/datasets'),
        api('/api/v1/health'),
        api('/api/v1/analyses'),
      ])
      setDatasets(ds)
      setHealth(he)
      setHistory(hi)
      return ds
    } catch (e) {
      if (!quiet) setError(e.message)
      return []
    }
  }

  useEffect(() => { refresh() }, [])

  useEffect(() => {
    if (!query.trim()) { setQueryContext(null); return undefined }
    const timer = setTimeout(async () => {
      try {
        const parsed = await api('/api/v1/query/parse', {
          method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ query, dataset_count: selectedIds.length })
        })
        setQueryContext(parsed)
      } catch { setQueryContext(null) }
    }, 280)
    return () => clearTimeout(timer)
  }, [query, selectedIds.length])

  async function applyAnalysisResult(final) {
    setResult(final)
    if (final?.source_datasets?.length) {
      setDatasets(prev => {
        const byId = new Map(prev.map(x => [x.id, x]))
        final.source_datasets.forEach(x => byId.set(x.id, x))
        return [...byId.values()]
      })
      setPrimaryId(final.source_datasets[0]?.id || null)
      setCompareId(final.source_datasets[1]?.id || null)
    }
    refresh()
  }

  useEffect(() => {
    if (!analysisId) return undefined
    let cancelled = false
    const seq = runSeq.current
    let timer
    const tick = async () => {
      try {
        const next = await api(`/api/v1/analyses/${analysisId}/status`)
        if (cancelled || seq !== runSeq.current) return
        setStatus(next)
        if (next.status === 'completed' || next.status === 'failed') {
          const final = await api(`/api/v1/analyses/${analysisId}/result`)
          if (!cancelled && seq === runSeq.current) {
            applyAnalysisResult(final)
            setStatus(final)
          }
          return
        }
        timer = setTimeout(tick, 700)
      } catch (e) {
        if (!cancelled && seq === runSeq.current) setError(e.message)
      }
    }
    tick()
    return () => { cancelled = true; clearTimeout(timer) }
  }, [analysisId])

  async function handleUpload(file, slot) {
    if (!file) return
    setBusyUpload(slot)
    setError('')
    try {
      const uploaded = await uploadDataset(file, 'auto')
      setDatasets(prev => [uploaded, ...prev.filter(x => x.id !== uploaded.id)])
      if (slot === 'primary') setPrimaryId(uploaded.id)
      else setCompareId(uploaded.id)
      setResult(null)
      setStatus(null)
    } catch (e) {
      setError(e.message)
    } finally {
      setBusyUpload(null)
    }
  }

  async function loadDemo() {
    setError('')
    try {
      const demo = await api('/api/v1/demo/load', { method: 'POST' })
      await refresh()
      const assam = demo.filter(d => d.filename.includes('Assam_'))
      setPrimaryId(assam.find(d => d.filename.includes('July'))?.id || assam[0]?.id || null)
      setCompareId(assam.find(d => d.filename.includes('August'))?.id || assam[1]?.id || null)
      setQuery(EXAMPLES[0].query)
      setResult(null)
      setStatus(null)
    } catch (e) { setError(e.message) }
  }

  async function run(q = query, ids = selectedIds) {
    const trimmed = (q || '').trim()
    if (!trimmed) return setError('Enter a question first.')
    if (!ids.length && !canRunWithoutUpload) return setError('Upload/select imagery, or use a query with a supported location and date range for automatic Sentinel retrieval.')
    const seq = ++runSeq.current
    setAskedQuestion(trimmed)
    setError('')
    setResult(null)
    setStatus({ status: 'queued', events: [] })
    try {
      const created = await api('/api/v1/analyses', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: trimmed, dataset_ids: ids, provider }),
      })
      if (seq !== runSeq.current) return
      if (created && created.answer) {
        setStatus(created)
        applyAnalysisResult(created)
      } else {
        setAnalysisId(created.analysis_id)
      }
    } catch (e) {
      if (seq !== runSeq.current) return
      setStatus(null)
      setError(e.message)
    }
  }

  function clear() {
    setQuery('')
    setResult(null)
    setStatus(null)
    setAnalysisId(null)
  }

  async function useExample(ex) {
    setResult(null)
    setStatus(null)
    let ds = datasets
    if (ds.length === 0) ds = await refresh(true)
    const id = name => (ds.find(d => d.filename === name) || {}).id || null
    const A_JUL = 'Assam_July_2025_S1_SAR_demo.tif'
    const A_AUG_O = 'Assam_August_2025_S2_optical_demo.tif'
    const A_AUG_S = 'Assam_August_2025_S1_SAR_demo.tif'
    const I_2023 = 'Indore_2023_optical.tif'
    const I_2026 = 'Indore_2026_optical.tif'
    let p = null
    let c = null
    if (ex.title.startsWith('Assam flood')) {
      p = id(A_JUL); c = id(A_AUG_S)
    } else if (ex.title.startsWith('Urban expansion')) {
      p = id(I_2023); c = id(I_2026)
    } else if (ex.title.startsWith('Vegetation loss')) {
      p = id(I_2023); c = id(I_2026)
    } else if (ex.title.startsWith('Vision assistant')) {
      p = id(A_AUG_O)
    } else if (ex.title.startsWith('Ground buildings')) {
      p = id(I_2026)
    } else if (ex.title.startsWith('Temporal visual')) {
      p = id(A_JUL); c = id(A_AUG_S)
    } else if (ex.title.startsWith('Optical + SAR')) {
      p = id(A_AUG_O); c = id(A_AUG_S)
    }
    setPrimaryId(p)
    setCompareId(c)
    setQuery(ex.query)
    if (p || c) run(ex.query, [p, c].filter(Boolean))
  }

  return (
    <ErrorBoundary>
      <div className="page-shell">
      <div className="top-utility">
        <StatusBadge health={health}/>
        <button className="utility-button" onClick={() => setAdvancedOpen(v => !v)}><Settings2 size={15}/> Runtime</button>
      </div>

      <Brand/>

      {advancedOpen && (
        <section className="advanced-bar anim-input">
          <div>
            <label>Agent runtime</label>
            <select value={provider} onChange={e => setProvider(e.target.value)}>
              <option value="auto">Auto — SatQuery planner + optional external bridge</option>
              <option value="external">Prefer external agent bridge</option>
              <option value="local">SatQuery local tool router</option>
            </select>
          </div>
          <div className="advanced-status">
            <span><Radio size={15}/> Core API <b>{health?.status === 'ok' ? 'online' : 'checking'}</b></span>
            <span><Cpu size={15}/> Flood model <b>{health?.flood_model?.ready ? 'pretrained U-Net ready' : 'adaptive fallback'}</b></span>
            <span><Sparkles size={15}/> Vision assistant <b className={health?.specialists?.vision_assistant?.ready ? 'status-ok' : ''}>{visionStatusText(health)}</b></span>
            <span><Radio size={15}/> SAR vision <b>{health?.specialists?.sar_vision_assistant?.reachable ? 'SARChat connected' : 'TEOChat / fallback'}</b></span>
            <span><Layers3 size={15}/> Text grounding <b>{health?.specialists?.text_segmentation?.reachable ? 'SamGeo connected' : 'optional'}</b></span>
            <span><Activity size={15}/> Change model <b>{health?.specialists?.trained_change_detection?.reachable ? 'Open-CD connected' : 'deterministic fallback'}</b></span>
            <span><ImageIcon size={15}/> Large-RSI VQA <b>{health?.specialists?.large_image_vision?.reachable ? 'LRS-VQA connected' : 'TEOChat / fallback'}</b></span>
            <span><Layers3 size={15}/> Optical+SAR fusion <b>{health?.specialists?.multimodal_fusion?.reachable ? 'TerraMind service connected' : 'semantic fallback'}</b></span>
            <span><Zap size={15}/> Agent bridge <b>{health?.agent_bridge?.reachable ? 'connected' : 'optional'}</b></span>
          </div>
        </section>
      )}

      {error && <div className="error-box"><AlertTriangle size={17}/><span>{error}</span><button onClick={() => setError('')}><X size={15}/></button></div>}

      <main className="analysis-grid">
        <section className="column left-column anim-input">
          <FieldLabel>Enter your question</FieldLabel>
          <textarea
            className="question-box"
            placeholder="Example: Show flooded areas around Assam between July and August 2025."
            value={query}
            onChange={e => setQuery(e.target.value)}
          />
          <QueryContext context={queryContext}/>
          <ImageSuggestions primary={primary} compare={compare} run={run} setQuery={setQuery}/>
          {queryContext?.supported === false && <div className="capability-warning"><ShieldCheck size={18}/><div><b>Capability not enabled</b><span>{queryContext.unsupported_reason}</span></div></div>}

          <div className="input-heading-row">
            <FieldLabel>Satellite imagery</FieldLabel>
            <button className="link-button" onClick={() => setLibraryOpen(v => !v)}><Database size={14}/> Choose existing</button>
          </div>

          {!primary && canRunWithoutUpload && (
            <div className="auto-retrieval-card">
              <CloudDownload size={20}/>
              <div><b>No upload needed</b><span>SatQuery will search and clip Sentinel-1 RTC scenes for the parsed place and periods when you submit.</span></div>
            </div>
          )}

          <InputImageCard
            dataset={primary}
            busy={busyUpload === 'primary'}
            onFile={file => handleUpload(file, 'primary')}
            onClear={() => { setPrimaryId(null); setResult(null) }}
            label="Primary / earlier imagery"
          />

          <CompareInput
            dataset={compare}
            busy={busyUpload === 'compare'}
            onFile={file => handleUpload(file, 'compare')}
            onClear={() => { setCompareId(null); setResult(null) }}
          />

          {libraryOpen && (
            <DatasetLibrary
              datasets={datasets}
              primaryId={primaryId}
              compareId={compareId}
              onPrimary={id => { setPrimaryId(id); if (compareId === id) setCompareId(null); setLibraryOpen(false); setResult(null) }}
              onCompare={id => { setCompareId(id); setLibraryOpen(false); setResult(null) }}
            />
          )}

          <div className="main-actions">
            <button className={`primary-action${running ? ' running' : ''}`} onClick={run} disabled={running || queryContext?.supported === false}>
              {running ? <LoaderCircle className="spin" size={18}/> : <Play size={17} fill="currentColor"/>}
              {running ? STAGE_LABELS[status?.status] || 'Running…' : (primaryId ? 'Analyze' : 'Retrieve & Analyze')}
            </button>
            <button className="secondary-action" onClick={clear}><RotateCcw size={16}/> Clear</button>
          </div>

          <div className="sample-title">Sample Queries</div>
          <div className="examples-list">
            {EXAMPLES.map((ex, idx) => (
              <button className="example-row" key={ex.title} onClick={() => useExample(ex)}>
                <span className="example-number">{idx + 1}</span>
                <span><b>{ex.title}</b><small>{ex.query}</small></span>
                <em>{ex.hint}</em>
              </button>
            ))}
          </div>
          <button className="demo-button" onClick={loadDemo}><Sparkles size={15}/> Load offline Assam temporal flood demo</button>
        </section>

        <section className="column right-column anim-output">
          <FieldLabel>Final Answer</FieldLabel>
          <AnswerBox result={result} status={status} askedQuestion={askedQuestion}/>

          <FieldLabel>Execution Trace</FieldLabel>
          <ExecutionTrace status={status} result={result}/>

          <FieldLabel>Geospatial Evidence</FieldLabel>
          <OutputPanel result={result} primary={primary} running={running} askedQuestion={askedQuestion}/>
        </section>
      </main>

      <EvidenceStrip result={result} primary={primary} compare={compare}/>
      <RecentAnalyses rows={history}/>

      <footer>
        <span>SatQuery AI · Natural-language Earth observation → sensor-aware analysis → GIS evidence → trusted answer.</span>
        <span>Model and confidence limitations are shown explicitly in every result.</span>
      </footer>
      </div>
    </ErrorBoundary>
  )
}

function FieldLabel({ children }) {
  return <label className="field-label">{children}</label>
}

function previewSrc(dataset, fallback = '') {
  return dataset?.preview_b64 || (dataset?.preview_url ? apiUrl(dataset.preview_url) : fallback) || ''
}

function InputImageCard({ dataset, busy, onFile, onClear, label }) {
  const ref = useRef(null)
  return (
    <div className={`image-input-card ${dataset ? 'has-image' : ''}`}>
      {dataset ? (
        <>
          <img src={previewSrc(dataset)} alt={dataset.filename}/>
          <div className="image-card-overlay">
            <div><b>{label}</b><span>{dataset.filename}</span></div>
            <button onClick={onClear} title="Remove"><X size={15}/></button>
          </div>
          <div className="image-meta-pills">{formatMeta(dataset).map(x => <span key={x}>{x}</span>)}</div>
          {dataset.metadata?.demo_data && <div className="demo-watermark">SYNTHETIC DEMO DATA</div>}
        </>
      ) : (
        <button className="upload-empty" onClick={() => ref.current?.click()} disabled={busy}>
          {busy ? <LoaderCircle className="spin" size={30}/> : <Upload size={30}/>} 
          <b>{busy ? 'Uploading…' : 'Drop or upload satellite imagery'}</b>
          <span>GeoTIFF, TIFF, PNG, JPG · or use auto retrieval from the query</span>
        </button>
      )}
      <input ref={ref} hidden type="file" accept=".tif,.tiff,.png,.jpg,.jpeg" onChange={e => { onFile(e.target.files?.[0]); e.target.value = '' }}/>
      {dataset && <button className="replace-image" onClick={() => ref.current?.click()}><Upload size={13}/> Replace</button>}
    </div>
  )
}

function CompareInput({ dataset, busy, onFile, onClear }) {
  const ref = useRef(null)
  if (!dataset) {
    return (
      <div className="compare-add-row">
        <button onClick={() => ref.current?.click()} disabled={busy}>
          {busy ? <LoaderCircle className="spin" size={15}/> : <Plus size={15}/>} Add second image for temporal comparison
        </button>
        <span>Optional</span>
        <input ref={ref} hidden type="file" accept=".tif,.tiff,.png,.jpg,.jpeg" onChange={e => { onFile(e.target.files?.[0]); e.target.value = '' }}/>
      </div>
    )
  }
  return (
    <div className="compare-mini">
      <img src={previewSrc(dataset)} alt={dataset.filename}/>
      <div><small>Comparison / later image</small><b>{dataset.filename}</b><span>{formatMeta(dataset).join(' · ')}</span></div>
      <button onClick={onClear}><X size={15}/></button>
    </div>
  )
}

function DatasetLibrary({ datasets, primaryId, compareId, onPrimary, onCompare }) {
  return (
    <div className="dataset-library">
      <div className="library-head"><b>Existing datasets</b><span>{datasets.length} available</span></div>
      {datasets.length === 0 ? <div className="library-empty">No uploaded datasets yet.</div> : datasets.map(d => (
        <div className="library-row" key={d.id}>
          <img src={previewSrc(d)} alt=""/>
          <div><b>{d.filename}</b><small>{formatMeta(d).join(' · ')}</small></div>
          <div className="library-actions">
            <button className={primaryId === d.id ? 'selected' : ''} onClick={() => onPrimary(d.id)}>Earlier</button>
            <button className={compareId === d.id ? 'selected' : ''} disabled={primaryId === d.id} onClick={() => onCompare(d.id)}>Later</button>
          </div>
        </div>
      ))}
    </div>
  )
}

function AnswerBox({ result, status, askedQuestion }) {
  const failed = status?.status === 'failed' || result?.error
  if (failed) return <div className="answer-box error-answer"><AlertTriangle size={18}/><span>{result?.error || 'Analysis failed. Review the execution trace.'}</span></div>
  if (!result) {
    return (
      <div className="answer-box empty-answer">
        {status ? <><LoaderCircle className="spin" size={18}/><span>{STAGE_LABELS[status.status] || 'SatQuery is working…'}</span></> : <span>The grounded final answer will appear here.</span>}
      </div>
    )
  }
  return (
    <div className="answer-box populated-answer">
      <div className="answer-asked">Asked: {askedQuestion || '—'}</div>
      <div className="answer-topline"><span className={`confidence-badge confidence-${result.confidence_label?.toLowerCase()}`}>{result.confidence_label} operational confidence · {Math.round((result.confidence || 0) * 100)}%</span><CopyButton text={result.answer}/></div>
      <p>{result.answer}</p>
      <div className="answer-source"><Sparkles size={14}/><span>SatQuery tool router · {result.provider === 'external_agent' ? 'external plan validated' : 'local plan'} · {result.method}</span></div>
    </div>
  )
}

function CopyButton({ text }) {
  const [done, setDone] = useState(false)
  async function copy() {
    try { await navigator.clipboard.writeText(text || ''); setDone(true); setTimeout(() => setDone(false), 1200) } catch { /* no-op */ }
  }
  return <button className="icon-text-button" onClick={copy}>{done ? <Check size={14}/> : <Copy size={14}/>} {done ? 'Copied' : 'Copy'}</button>
}

function ExecutionTrace({ status, result }) {
  const events = result?.events || status?.events || []
  return (
    <div className="trace-box">
      <div className="trace-toolbar"><Terminal size={15}/><span>{status?.status ? STAGE_LABELS[status.status] : 'Waiting for submission'}</span>{status && !['completed', 'failed'].includes(status.status) && <LoaderCircle className="spin" size={14}/>}</div>
      <div className="trace-content">
        {events.length === 0 ? <div className="trace-placeholder">Intent, satellite retrieval, sensor routing, tool calls and evidence checks will stream here.</div> : events.map((e, i) => (
          <div className={`trace-line ${e.state || ''}${i === events.length - 1 && !['completed', 'failed'].includes(e.state) ? ' new-flash' : ''}`} key={`${e.ts}-${i}`}>
            <span className="trace-index">{String(i + 1).padStart(2, '0')}</span>
            <span className="trace-icon">{e.state === 'error' ? '×' : e.state === 'warning' ? '!' : '✓'}</span>
            <div><b>{e.title}</b><small>{e.detail}</small></div>
            <time>{formatDate(e.ts)}</time>
          </div>
        ))}
      </div>
    </div>
  )
}

function OutputPanel({ result, primary, running, askedQuestion }) {
  const [tab, setTab] = useState('map')
  const src = result?.overlay_b64 || (result?.overlay_url ? apiUrl(result.overlay_url) : previewSrc(primary, null))
  const geojsonHref = result?.geojson ? 'data:application/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(result.geojson)) : (result?.geojson_url ? apiUrl(result.geojson_url) : null)
  const mapReady = Boolean(result?.map_context?.bounds_wgs84)
  useEffect(() => { if (!mapReady && tab === 'map') setTab('image') }, [mapReady, tab])
  return (
    <div className={`output-panel-wrap${running ? ' running' : ''}`}>
      <div className="output-tabs">
        <button className={tab === 'map' ? 'active' : ''} disabled={!mapReady} onClick={() => setTab('map')}><MapIcon size={14}/> Interactive Map</button>
        <button className={tab === 'image' ? 'active' : ''} onClick={() => setTab('image')}><ImageIcon size={14}/> Evidence Image</button>
      </div>
      <div className="output-image-box">
        {tab === 'map' && result ? <GeoEvidenceMap result={result}/> : (
          src ? <img src={src} alt="Analysis output"/> : <div className="output-empty"><ImageIcon size={34}/><b>Geospatial output</b><span>Map and annotated evidence will appear here after analysis.</span></div>
        )}
        {(result?.overlay_b64 || result?.overlay_url) && (
          <div className="output-actions">
            <a href={result.overlay_b64 || apiUrl(result.overlay_url)} target="_blank" rel="noreferrer" download={result.overlay_b64 ? 'overlay.png' : undefined}><Download size={14}/> Image</a>
            {geojsonHref && <a href={geojsonHref} target="_blank" rel="noreferrer" download="result.geojson"><FileJson size={14}/> GeoJSON</a>}
          </div>
        )}
      </div>
      {result?.legend?.length > 0 && <div className="map-legend">{result.legend.map(x => <span key={x.label}><i style={{ background: x.color }}/>{x.label}</span>)}</div>}
    </div>
  )
}

function EvidenceStrip({ result, primary, compare }) {
  if (!primary && !result) return null
  const stats = result?.statistics ? Object.entries(result.statistics) : []
  const ctx = result?.query_context
  const prov = result?.provenance || {}
  const breakdown = result?.confidence_breakdown || {}
  const modelBacked = Boolean(prov.model_backed ?? result?.model_info?.model_backed ?? result?.model_info?.before?.model_backed)
  const sourceText = prov.sources?.length
    ? prov.sources.map(s => `${s.modality?.toUpperCase() || 'DATA'} · ${s.acquired_at || 'date n/a'}`).join('  →  ')
    : (compare ? `Compared with ${compare.filename}` : formatMeta(primary).join(' · '))
  const components = [
    ['Input quality', breakdown.input_quality],
    ['Model support', breakdown.model_support],
    ['Spatial support', breakdown.spatial_support],
    ['Temporal support', breakdown.temporal_support],
    ['Evidence coverage', breakdown.evidence_coverage],
  ].filter(([,v]) => typeof v === 'number')
  return (
    <section className="evidence-section anim-evidence">
      <div className="section-title-row"><div><span>Grounded analysis</span><h3>Evidence, confidence & provenance</h3></div><div className="section-line"/></div>
      <div className="evidence-grid">
        <InfoCard icon={MapIcon} title="Parsed request" value={ctx?.location?.name || result?.map_context?.location || 'Uploaded AOI'} detail={ctx?.date_range ? `${ctx.date_range.start_date} → ${ctx.date_range.end_date}` : 'Using selected imagery'}/>
        <InfoCard icon={Satellite} title="Source imagery" value={primary?.filename || result?.source_datasets?.[0]?.filename || '—'} detail={sourceText}/>
        <InfoCard icon={Cpu} title="Model / method" value={prov.model_display || result?.method || 'Tool-selected'} detail={modelBacked ? 'Specialist model-backed inference' : 'Transparent fallback / deterministic analysis'}/>
        {prov.model_version ? <InfoCard icon={Cpu} title="Model version" value={prov.model_version} detail={prov.model_backend === 'teochat' ? 'TEOChat checkpoint' : 'HQ checkpoint · deterministic inference'}/> : null}
        {prov.latency_ms != null && !Number.isNaN(prov.latency_ms) ? <InfoCard icon={Zap} title="Inference time" value={prov.latency_ms >= 1000 ? `${(prov.latency_ms / 1000).toFixed(1)} s` : `${prov.latency_ms} ms`} detail={prov.model_backed ? 'Model inference latency' : 'Processing time (statistics baseline)'}/> : null}
        <InfoCard icon={ShieldCheck} title="Fallback status" value={prov.fallback_used ? 'Fallback used' : 'Model-backed'} detail={prov.fallback_used ? 'Result remains usable, but specialist-model accuracy is not claimed.' : 'A configured specialist model produced the primary inference.'}/>
        <InfoCard icon={CheckCircle2} title="Evidence gate" value={result ? `${result.confidence_label} · ${Math.round((result.confidence || 0) * 100)}%` : 'Pending'} detail="Operational confidence; not a calibrated scientific probability"/>
        <InfoCard icon={Layers3} title="Geo outputs" value={result ? `${result.geojson?.features?.length || 0} vector feature(s)` : 'Pending'} detail="Interactive map + overlay + GeoJSON polygons"/>
      </div>
      {components.length > 0 && <div className="confidence-breakdown">
        <div className="confidence-breakdown-head"><Gauge size={16}/><div><b>Confidence breakdown</b><span>{breakdown.note}</span></div></div>
        <div className="confidence-bars">{components.map(([label, value]) => <div className="confidence-row" key={label}><span>{label}</span><div><i style={{width: `${Math.round(value*100)}%`}}/></div><b>{Math.round(value*100)}%</b></div>)}</div>
      </div>}
      {prov.benchmark && <div className="benchmark-note"><Activity size={15}/><div><b>Upstream flood-model benchmark</b><span>IoU {prov.benchmark.iou} · F1 {prov.benchmark.f1} · Precision {prov.benchmark.precision} · Recall {prov.benchmark.recall} · Accuracy {prov.benchmark.accuracy}. {prov.benchmark.important}</span></div></div>}
      {stats.length > 0 && <div className="stats-row">{stats.slice(0, 9).map(([k, v]) => <div key={k}><small>{k.replaceAll('_', ' ')}</small><b>{typeof v === 'number' ? Number(v).toLocaleString() : String(v)}</b></div>)}</div>}
      {result?.warnings?.length > 0 && <div className="warning-list">{result.warnings.map((w, i) => <span key={i}><AlertTriangle size={13}/>{w}</span>)}</div>}
    </section>
  )
}

function InfoCard({ icon: Icon, title, value, detail }) {
  return <div className="info-card"><div className="info-icon"><Icon size={18}/></div><div><small>{title}</small><b>{value}</b><p>{detail}</p></div></div>
}

function RecentAnalyses({ rows }) {
  const [open, setOpen] = useState(false)
  if (!rows?.length) return null
  return (
    <section className="recent-section">
      <button className="recent-toggle" onClick={() => setOpen(v => !v)}><div><Database size={16}/><span>Recent analyses</span><em>{rows.length}</em></div><ChevronDown size={16} className={open ? 'flip' : ''}/></button>
      {open && <div className="recent-list">{rows.slice(0, 8).map(r => <div key={r.id}><span className={`mini-status ${r.status}`}/><b>{r.query}</b><small>{r.intent || 'pending'} · {r.provider || 'auto'}</small></div>)}</div>}
    </section>
  )
}

export default App
