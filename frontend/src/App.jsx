import { useState, useEffect } from 'react'
import CandidateCard from './components/CandidateCard'
import SourcedList from './components/SourcedList'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export default function App() {
  // ─── Form State ─────────────────────────────────────────────────
  const [role, setRole] = useState('')
  const [location, setLocation] = useState('')
  const [persona, setPersona] = useState('')

  // ─── Stage State (2 stages now) ─────────────────────────────────
  const [stage1Status, setStage1Status] = useState('idle')   // idle | running | done | error
  const [stage2Status, setStage2Status] = useState('idle')
  const [statusMsg, setStatusMsg] = useState('')
  const [actionStartTime, setActionStartTime] = useState(0)

  // ─── Data ───────────────────────────────────────────────────────
  const [sourced, setSourced] = useState([])
  const [results, setResults] = useState([])

  // ─── Polling & Data Sync ───────────────────────────────────────
  const fetchData = async () => {
    try {
      // 1. Fetch Status
      const statusRes = await fetch(`${API}/status?t=${Date.now()}`)
      if (statusRes.ok) {
        const d = await statusRes.json()

        setStatusMsg(d.message || '')
        const stage = (d.stage || '').toLowerCase()

        if (stage === 'sourcing') setStage1Status('running')
        else if (stage === 'sourcing_done') setStage1Status('done')
        else if (stage === 'analyzing') setStage2Status('running')
        else if (stage === 'done') setStage2Status('done')
        else if (stage === 'error') {
          if (stage1Status === 'running') setStage1Status('error')
          if (stage2Status === 'running') setStage2Status('error')
        }
      }

      // 2. Fetch Data
      const [sRes, resRes] = await Promise.all([
        fetch(`${API}/sourced?t=${Date.now()}`),
        fetch(`${API}/results?t=${Date.now()}`)
      ])

      if (sRes.ok) { const d = await sRes.json(); setSourced(d.sourced || []) }
      if (resRes.ok) { const d = await resRes.json(); setResults(d.results || []) }

    } catch (err) {
      console.error("Fetch error:", err)
    }
  }

  // Load data on mount
  useEffect(() => {
    fetchData()
  }, [])

  // Poll when something is running
  useEffect(() => {
    const anyRunning = stage1Status === 'running' || stage2Status === 'running'
    if (!anyRunning) return

    const id = setInterval(fetchData, 3000)
    return () => clearInterval(id)
  }, [stage1Status, stage2Status, actionStartTime])

  // ─── Actions ────────────────────────────────────────────────────
  const startSourcing = async () => {
    if (!role.trim()) return alert('Enter a target role first.')
    setStage1Status('running')
    setSourced([]); setResults([])
    setStatusMsg('Starting sourcing...')
    setActionStartTime(Date.now())
    setStage2Status('idle')
    try {
      localStorage.setItem('last_search_role', role.trim())
      const res = await fetch(`${API}/start-sourcing`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ role: role.trim(), location: location.trim() || 'Pakistan', search_depth: 50 }),
      })
      if (!res.ok) throw new Error((await res.json()).detail)
    } catch (err) {
      setStage1Status('error')
      setStatusMsg(`❌ ${err.message}`)
    }
  }

  const startAnalyze = async () => {
    if (!persona.trim()) return alert('Describe an ideal candidate persona first.')
    setStage2Status('running')
    setStatusMsg('Running AI assessment...')
    setResults([])
    setActionStartTime(Date.now())
    try {
      const res = await fetch(`${API}/start-analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ role: role.trim(), persona: persona.trim() }),
      })
      if (!res.ok) throw new Error((await res.json()).detail)
    } catch (err) {
      setStage2Status('error')
      setStatusMsg(`❌ ${err.message}`)
    }
  }

  const checkReplies = async () => {
    setStatusMsg('Checking LinkedIn Inbox for replies...')
    try {
      const res = await fetch(`${API}/check-replies`, { method: 'POST' })
      const data = await res.json()
      setStatusMsg(`✅ Inbox check complete. ${data.replies_found} new replies detected.`)
    } catch (err) {
      setStatusMsg('❌ Failed to check inbox.')
    }
  }

  // ─── Render ─────────────────────────────────────────────────────
  return (
    <div className="min-h-screen">
      {/* ═══ Header ═══════════════════════════════════════════════ */}
      <header className="sticky top-0 z-50 border-b border-slate-800/60 bg-slate-950/80 backdrop-blur-xl">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 bg-gradient-to-br from-brand-500 to-purple-600 rounded-xl flex items-center justify-center shadow-lg shadow-brand-500/25">
              <span className="text-base font-black text-white">TS</span>
            </div>
            <h1 className="text-lg font-bold bg-clip-text text-transparent bg-gradient-to-r from-brand-400 to-purple-400">
              TalentScout
            </h1>
          </div>
          <div className="flex items-center gap-4">
            <button
              onClick={checkReplies}
              className="px-4 py-1.5 rounded-lg border border-slate-800 text-slate-400 text-[11px] font-bold hover:bg-slate-900 transition-all flex items-center gap-2"
            >
              <span>📩</span> Check Replies
            </button>
            <span className="text-[10px] font-mono text-slate-600 bg-slate-900 px-2 py-1 rounded-lg border border-slate-800">
              v6.0 · 2-Stage Pipeline
            </span>
          </div>
        </div>
      </header>

      {/* ═══ Main ═════════════════════════════════════════════════ */}
      <main className="max-w-7xl mx-auto px-6 py-8 space-y-8">

        {/* ─── Input Fields ─────────────────────────────────── */}
        <section className="glass-card p-1">
          <div className="bg-slate-950/50 rounded-xl p-6 space-y-5">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-slate-400 ml-1">Target Role *</label>
                <input
                  type="text"
                  value={role}
                  onChange={e => setRole(e.target.value)}
                  placeholder="e.g. AI Agent Developer"
                  className="input-field"
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-slate-400 ml-1">Location</label>
                <input
                  type="text"
                  value={location}
                  onChange={e => setLocation(e.target.value)}
                  placeholder="e.g. Pakistan"
                  className="input-field"
                />
              </div>
            </div>
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-slate-400 ml-1">Ideal Candidate Persona *</label>
              <textarea
                value={persona}
                onChange={e => setPersona(e.target.value)}
                placeholder="Describe your ideal candidate: skills, experience level, traits, industry background..."
                rows={3}
                className="input-field resize-none"
              />
            </div>
          </div>
        </section>

        {/* ─── Status Banner ──────────────────────────────────── */}
        {statusMsg && (
          <div className="glass-card px-5 py-3 flex items-center gap-3 border-brand-500/20 animate-fade-in">
            <div className="w-2 h-2 bg-brand-500 rounded-full animate-pulse" />
            <span className="text-sm text-slate-300">{statusMsg}</span>
          </div>
        )}

        {/* ═══════════════════════════════════════════════════════
            STAGE 1: SOURCING
        ═══════════════════════════════════════════════════════ */}
        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-bold flex items-center gap-3">
              <span className="w-8 h-8 bg-blue-500/10 text-blue-400 rounded-lg flex items-center justify-center text-sm border border-blue-500/20">1</span>
              <span>Source Candidates</span>
            </h2>
            <div className="flex items-center gap-3">
              {sourced.length > 0 && (
                <span className="badge bg-blue-500/10 text-blue-400 border border-blue-500/20 text-xs px-3 py-1">
                  {sourced.length} found
                </span>
              )}
              <button
                onClick={startSourcing}
                disabled={stage1Status === 'running'}
                className="btn-primary text-sm px-4 py-2 flex items-center gap-2"
              >
                {stage1Status === 'running' ? (
                  <><div className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" /> Sourcing...</>
                ) : stage1Status === 'done' ? (
                  <>✅ Re-Source</>
                ) : (
                  <>🌍 Start Sourcing</>
                )}
              </button>
            </div>
          </div>

          <SourcedList candidates={sourced} />
        </section>

        {/* ═══════════════════════════════════════════════════════
            STAGE 2: AI ANALYZE (Assessment)
        ═══════════════════════════════════════════════════════ */}
        {stage1Status === 'done' && sourced.length > 0 && (
          <section className="space-y-4 animate-slide-up">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-bold flex items-center gap-3">
                <span className="w-8 h-8 bg-emerald-500/10 text-emerald-400 rounded-lg flex items-center justify-center text-sm border border-emerald-500/20">2</span>
                <span>AI Analysis</span>
                <span className="text-sm font-normal text-slate-500">— Deep assessment</span>
              </h2>
              <div className="flex items-center gap-3">
                {results.length > 0 && (
                  <span className="badge bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-xs px-3 py-1">
                    {results.length} analyzed
                  </span>
                )}
                <button
                  onClick={startAnalyze}
                  disabled={stage2Status === 'running'}
                  className="btn-primary text-sm px-4 py-2 flex items-center gap-2"
                  style={{ background: 'linear-gradient(135deg, #10b981, #059669)' }}
                >
                  {stage2Status === 'running' ? (
                    <><div className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" /> Analyzing...</>
                  ) : stage2Status === 'done' ? (
                    <>✅ Re-Analyze</>
                  ) : (
                    <>🤖 Start AI Analysis</>
                  )}
                </button>
              </div>
            </div>

            {stage2Status === 'running' && results.length === 0 && (
              <div className="text-center py-12 text-slate-600 glass-card border-dashed">
                <div className="text-4xl mb-3 opacity-50">🤖</div>
                <p className="text-sm">Running AI assessment on each candidate...</p>
                <p className="text-xs text-slate-700 mt-1">This may take 1-3 minutes.</p>
              </div>
            )}

            {/* Final Results */}
            {results.length > 0 && (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                {results.map((r, i) => (
                  <CandidateCard key={i} result={r} />
                ))}
              </div>
            )}
          </section>
        )}

        {/* ─── Empty State ───────────────────────────────────── */}
        {stage1Status === 'idle' && (
          <div className="text-center py-24 animate-fade-in">
            <div className="text-7xl mb-6 opacity-20">🎯</div>
            <h2 className="text-2xl font-bold text-slate-400 mb-3">Ready to Scout</h2>
            <p className="text-slate-600 max-w-lg mx-auto leading-relaxed">
              Enter a role and location above, then click
              <strong className="text-blue-400"> Start Sourcing</strong>.
              You control each step manually.
            </p>
          </div>
        )}
      </main>

      {/* ═══ Footer ═══════════════════════════════════════════════ */}
      <footer className="border-t border-slate-900 mt-16 py-6 text-center text-xs text-slate-700">
        TalentScout AI v6.0 · 2-Stage Pipeline · Powered by Cerebras + HarvestAPI
      </footer>
    </div>
  )
}