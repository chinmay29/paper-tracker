/**
 * Paper card component for list view with scoring display
 */
function PaperCard({ paper, onClick }) {
    const formatDate = (isoString) => {
        const date = new Date(isoString);
        return date.toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
        });
    };

    // Tier styling
    const getTierStyle = (tier) => {
        const styles = {
            'S': { background: 'linear-gradient(135deg, #ffd700, #ff8c00)', color: '#000', boxShadow: '0 0 10px rgba(255,215,0,0.5)' },
            'A': { background: 'linear-gradient(135deg, #a855f7, #7c3aed)', color: '#fff' },
            'B': { background: 'linear-gradient(135deg, #3b82f6, #2563eb)', color: '#fff' },
            'C': { background: 'linear-gradient(135deg, #22c55e, #16a34a)', color: '#fff' },
            'D': { background: 'rgba(100, 116, 139, 0.3)', color: '#94a3b8' },
        };
        return styles[tier] || styles['D'];
    };

    // Topic category display names
    const categoryLabels = {
        'quantization': '🔢 Quantization',
        'kv_cache': '💾 KV Cache',
        'speculative_decoding': '⚡ Speculative',
        'batching': '📦 Batching',
        'parallelism': '🔀 Parallelism',
        'memory_optimization': '🧠 Memory',
        'serving': '🖥️ Serving',
        'efficiency': '⚙️ Efficiency',
    };

    const tier = paper.rank_tier || '';
    const score = paper.composite_score || 0;
    const topicCategory = paper.topic_category || '';
    const hasScoring = tier && score > 0;

    return (
        <article className="paper-card" onClick={onClick}>
            <div className="paper-header">
                {hasScoring && (
                    <div className="paper-score-badge" style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px',
                        marginBottom: '8px'
                    }}>
                        <span style={{
                            ...getTierStyle(tier),
                            padding: '4px 12px',
                            borderRadius: '6px',
                            fontWeight: 'bold',
                            fontSize: '14px',
                            letterSpacing: '1px'
                        }}>
                            {tier}
                        </span>
                        <span style={{
                            color: '#94a3b8',
                            fontSize: '13px'
                        }}>
                            Score: {score.toFixed(1)}
                        </span>
                        {topicCategory && categoryLabels[topicCategory] && (
                            <span style={{
                                background: 'rgba(139, 92, 246, 0.15)',
                                border: '1px solid rgba(139, 92, 246, 0.3)',
                                color: '#a78bfa',
                                padding: '2px 8px',
                                borderRadius: '4px',
                                fontSize: '12px'
                            }}>
                                {categoryLabels[topicCategory]}
                            </span>
                        )}
                        {paper.benchmark_flags && paper.benchmark_flags.length > 0 && (
                            <span style={{
                                background: 'rgba(239, 68, 68, 0.15)',
                                border: '1px solid rgba(239, 68, 68, 0.3)',
                                color: '#ef4444',
                                padding: '2px 6px',
                                borderRadius: '4px',
                                fontSize: '11px'
                            }} title={paper.benchmark_flags.join(', ')}>
                                ⚠️ {paper.benchmark_flags.length}
                            </span>
                        )}
                    </div>
                )}
                <h3 className="paper-title">{paper.title}</h3>
            </div>

            <div className="paper-meta">
                <span className="paper-tag category">{paper.primary_category}</span>
                <span className="paper-tag date">📅 {formatDate(paper.published)}</span>
                {paper.citation_count > 0 && (
                    <span className="paper-tag citations">
                        📊 {paper.citation_count} citations
                    </span>
                )}
                {paper.has_code && (
                    <span className="paper-tag" style={{
                        background: 'rgba(16, 185, 129, 0.15)',
                        borderColor: 'rgba(16, 185, 129, 0.3)',
                        color: '#10b981'
                    }}>
                        💻 Code
                    </span>
                )}
            </div>

            <p className="paper-authors">{paper.authors_str}</p>

            <p className="paper-abstract">{paper.abstract}</p>

            <div className="paper-actions" onClick={(e) => e.stopPropagation()}>
                <a
                    href={paper.pdf_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="paper-link"
                >
                    📄 PDF
                </a>
                <a
                    href={paper.arxiv_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="paper-link"
                >
                    🔗 arXiv
                </a>
                {paper.github_url && (
                    <a
                        href={paper.github_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="paper-link"
                    >
                        💻 GitHub
                    </a>
                )}
            </div>
        </article>
    );
}

export default PaperCard;

