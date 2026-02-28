import { useState } from 'react'

export default function CandidateCard({ result }) {
    const [isMessaging, setIsMessaging] = useState(false)
    const [messageText, setMessageText] = useState('')
    const [isSending, setIsSending] = useState(false)
    const [status, setStatus] = useState(null)

    const score = result.overall_score ?? 0
    const scoreColor = score >= 80 ? 'text-emerald-400' : score >= 60 ? 'text-amber-400' : 'text-slate-400'
    const borderGlow = score >= 80 ? 'border-emerald-500/30 shadow-emerald-500/5' : 'border-slate-800/60'
    const tierColors = {
        1: 'bg-brand-500/20 text-brand-300 border-brand-500/30',
        2: 'bg-amber-500/15 text-amber-300 border-amber-500/25',
        3: 'bg-slate-700/40 text-slate-400 border-slate-600/30',
    }
    const actionColors = {
        'Shortlist': 'bg-emerald-500/15 text-emerald-300 border-emerald-500/25',
        'Review': 'bg-blue-500/15 text-blue-300 border-blue-500/25',
        'Hold': 'bg-amber-500/15 text-amber-300 border-amber-500/25',
        'Reject': 'bg-rose-500/15 text-rose-300 border-rose-500/25',
    }

    const strengths = result.role_fit_analysis?.strengths || []
    const gaps = result.role_fit_analysis?.gaps || []

    const openMessaging = async () => {
        setIsMessaging(true)
        setStatus('Generating personalized message...')
        try {
            const role = localStorage.getItem('last_search_role') || 'Software Engineer'
            const resp = await fetch(`http://localhost:8000/generate-message?candidate_id=${encodeURIComponent(result.candidate_id)}&role=${encodeURIComponent(role)}`)
            const data = await resp.json()
            setMessageText(data.message)
            setStatus(null)
        } catch (err) {
            console.error(err)
            setMessageText(`Hi, I saw your profile and would love to chat about a role!`)
            setStatus(null)
        }
    }

    const sendMessage = async () => {
        setIsSending(true)
        setStatus('Launching Phantom...')
        try {
            const resp = await fetch('http://localhost:8000/send-outreach', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    candidate_id: result.candidate_id,
                    personalized_message: messageText
                })
            })
            if (resp.ok) {
                setStatus('✅ Message Request Sent!')
                setTimeout(() => {
                    setIsMessaging(false)
                    setStatus(null)
                }, 2000)
            } else {
                setStatus('❌ Failed to send.')
            }
        } catch (err) {
            setStatus('❌ Error connecting to backend.')
        } finally {
            setIsSending(false)
        }
    }

    return (
        <div className={`glass-card-hover p-5 ${borderGlow} animate-slide-up relative overflow-hidden`}>
            {/* Header */}
            <div className="flex justify-between items-start mb-4">
                <div className="flex items-center gap-3 min-w-0">
                    <div className="w-11 h-11 bg-gradient-to-br from-brand-600 to-purple-600 rounded-xl flex items-center justify-center text-lg font-bold shrink-0 shadow-lg shadow-brand-500/20">
                        {(result.candidate_name || result.candidate_id || '?')[0].toUpperCase()}
                    </div>
                    <div className="min-w-0">
                        <h3 className="font-bold text-slate-100 truncate text-base">
                            {result.candidate_name || result.candidate_id}
                        </h3>
                        <div className="flex gap-1.5 mt-1 flex-wrap">
                            <span className={`badge border ${tierColors[result.tier] || tierColors[3]}`}>
                                Tier {result.tier}
                            </span>
                            <span className={`badge border ${actionColors[result.recommended_action] || actionColors['Hold']}`}>
                                {result.recommended_action}
                            </span>
                        </div>
                    </div>
                </div>

                {/* Score Circle */}
                <div className="flex flex-col items-center shrink-0 ml-3">
                    <div className={`text-3xl font-black ${scoreColor} leading-none`}>
                        {score}
                    </div>
                    <div className="text-[9px] text-slate-500 uppercase font-bold tracking-widest mt-1">Score</div>
                </div>
            </div>

            {/* Reasoning */}
            <p className="text-sm text-slate-300 leading-relaxed bg-slate-950/40 p-3.5 rounded-xl border border-slate-800/40 mb-4">
                {result.reasoning_summary}
            </p>

            {/* Evidence */}
            {
                result.role_fit_analysis?.evidence && (
                    <div className="mb-4 bg-brand-500/5 border border-brand-500/10 rounded-xl p-3.5">
                        <h4 className="text-[10px] font-bold text-brand-400 uppercase tracking-widest mb-1.5 flex items-center gap-1.5">
                            <span>🔍</span> Evidence
                        </h4>
                        <p className="text-xs text-slate-400 font-mono leading-relaxed">
                            {result.role_fit_analysis.evidence}
                        </p>
                    </div>
                )
            }

            {/* Strengths & Gaps */}
            <div className="grid grid-cols-2 gap-4">
                <div>
                    <span className="text-slate-500 text-xs font-medium block mb-2">Strengths</span>
                    <div className="flex flex-wrap gap-1.5">
                        {strengths.slice(0, 3).map((s, i) => (
                            <span key={i} className="chip bg-emerald-500/10 text-emerald-400 border-emerald-500/20 text-[11px]">
                                {s}
                            </span>
                        ))}
                        {strengths.length === 0 && <span className="text-slate-600 text-xs italic">—</span>}
                    </div>
                </div>
                <div>
                    <span className="text-slate-500 text-xs font-medium block mb-2">Gaps</span>
                    <div className="flex flex-wrap gap-1.5">
                        {gaps.slice(0, 3).map((g, i) => (
                            <span key={i} className="chip bg-rose-500/10 text-rose-400 border-rose-500/20 text-[11px]">
                                {g}
                            </span>
                        ))}
                        {gaps.length === 0 && <span className="text-slate-600 text-xs italic">—</span>}
                    </div>
                </div>
            </div>

            <div className="mt-4 pt-4 border-t border-slate-800 flex justify-between items-center">
                <div className="flex flex-wrap gap-1.5">
                    {result.risk_flags?.map((flag, i) => (
                        <span key={i} className="text-[10px] text-amber-400/70 bg-amber-500/5 px-2 py-0.5 rounded border border-amber-500/10">
                            ⚠ {flag}
                        </span>
                    ))}
                </div>

                <button
                    onClick={openMessaging}
                    className="flex items-center gap-2 bg-brand-600 hover:bg-brand-500 text-white text-[11px] font-bold px-4 py-2 rounded-lg transition-all shadow-lg shadow-brand-500/20"
                >
                    <span>✉</span> Reach Out
                </button>
            </div>

            {/* Messaging Modal Overlay */}
            {isMessaging && (
                <div className="absolute inset-0 bg-slate-950/95 backdrop-blur-md z-10 p-5 flex flex-col animate-fade-in">
                    <div className="flex justify-between items-center mb-4">
                        <h4 className="text-brand-400 font-bold text-xs uppercase tracking-widest">Personalized Outreach</h4>
                        <button onClick={() => setIsMessaging(false)} className="text-slate-500 hover:text-white">✕</button>
                    </div>

                    {status && <div className="text-[10px] text-brand-300 mb-2 animate-pulse">{status}</div>}

                    <textarea
                        value={messageText}
                        onChange={(e) => setMessageText(e.target.value)}
                        className="flex-1 bg-slate-900 border border-slate-700 rounded-xl p-3 text-sm text-slate-200 resize-none focus:outline-none focus:border-brand-500/50 mb-4 font-sans leading-relaxed"
                    />

                    <div className="flex gap-2">
                        <button
                            onClick={() => setIsMessaging(false)}
                            className="flex-1 px-4 py-2 rounded-lg border border-slate-700 text-slate-400 text-[11px] font-bold hover:bg-slate-800 transition-all"
                        >
                            Cancel
                        </button>
                        <button
                            onClick={sendMessage}
                            disabled={isSending}
                            className="flex-[2] px-4 py-2 rounded-lg bg-brand-600 text-white text-[11px] font-bold hover:bg-brand-500 transition-all shadow-lg shadow-brand-500/20 disabled:opacity-50"
                        >
                            {isSending ? 'Sending...' : 'Send via LinkedIn'}
                        </button>
                    </div>
                </div>
            )}
        </div >
    )
}
