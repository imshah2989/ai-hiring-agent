export default function DeepScrapeView({ candidates }) {
    if (!candidates || candidates.length === 0) {
        return (
            <div className="text-center py-16 text-slate-600 glass-card border-dashed">
                <div className="text-4xl mb-3 opacity-50">🕵️</div>
                <p className="text-sm">Waiting for deep scrape data...</p>
                <p className="text-xs mt-1 text-slate-700">The automation is processing each profile for deep analysis.</p>
            </div>
        )
    }

    return (
        <div className="space-y-4">
            {candidates.map((cand, i) => {
                const hasExperience = cand.experience_text && cand.experience_text.length > 5
                const hasAbout = cand.about && cand.about.length > 5

                return (
                    <div
                        key={i}
                        className="glass-card-hover overflow-hidden animate-slide-up"
                        style={{ animationDelay: `${i * 100}ms` }}
                    >
                        {/* Header */}
                        <div className="p-5 flex items-start gap-4 border-b border-slate-800/40">
                            <div className="w-12 h-12 bg-gradient-to-br from-brand-600 to-purple-600 rounded-xl flex items-center justify-center text-lg font-bold shrink-0 shadow-lg shadow-brand-500/20">
                                {(cand.name || '?')[0].toUpperCase()}
                            </div>
                            <div className="min-w-0 flex-1">
                                <div className="flex items-center gap-2 flex-wrap">
                                    <h3 className="font-bold text-base text-slate-100">{cand.name || 'Unknown'}</h3>
                                    {cand.is_open_to_work && (
                                        <span className="badge bg-emerald-500/15 text-emerald-400 border border-emerald-500/20">
                                            Open to Work
                                        </span>
                                    )}
                                    <span className="badge bg-brand-500/10 text-brand-400 border border-brand-500/20">
                                        ✓ Scraped
                                    </span>
                                </div>
                                <p className="text-sm text-slate-400 mt-1 truncate">{cand.headline || ''}</p>
                                {cand.location && (
                                    <p className="text-xs text-slate-500 mt-0.5">📍 {cand.location}</p>
                                )}
                            </div>
                            {cand.profile_url && (
                                <a
                                    href={cand.profile_url}
                                    target="_blank"
                                    rel="noreferrer"
                                    className="shrink-0 text-xs font-medium text-brand-400 hover:text-brand-300 bg-brand-500/10 hover:bg-brand-500/20 px-3 py-1.5 rounded-lg border border-brand-500/20 transition-all"
                                >
                                    View Profile ↗
                                </a>
                            )}
                        </div>

                        {/* Body */}
                        <div className="p-5 space-y-4">
                            {/* About */}
                            {hasAbout && (
                                <div>
                                    <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">About</h4>
                                    <p className="text-sm text-slate-300 leading-relaxed bg-slate-950/40 p-3 rounded-xl border border-slate-800/30 line-clamp-4">
                                        {cand.about}
                                    </p>
                                </div>
                            )}

                            {/* Experience */}
                            {hasExperience && (
                                <div>
                                    <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Experience</h4>
                                    <div className="text-sm text-slate-300 leading-relaxed bg-slate-950/40 p-3 rounded-xl border border-slate-800/30 max-h-48 overflow-y-auto whitespace-pre-wrap font-mono text-xs">
                                        {cand.experience_text}
                                    </div>
                                </div>
                            )}

                            {/* Education */}
                            {cand.education_text && cand.education_text.length > 5 && (
                                <div>
                                    <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Education</h4>
                                    <p className="text-sm text-slate-300 bg-slate-950/40 p-3 rounded-xl border border-slate-800/30">
                                        {cand.education_text}
                                    </p>
                                </div>
                            )}

                            {/* No data yet */}
                            {!hasExperience && !hasAbout && (
                                <div className="flex items-center gap-2 text-slate-500 text-sm py-2">
                                    <div className="w-4 h-4 border-2 border-slate-600 border-t-brand-500 rounded-full animate-spin" />
                                    Awaiting profile data...
                                </div>
                            )}
                        </div>
                    </div>
                )
            })}
        </div>
    )
}
