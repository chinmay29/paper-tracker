/**
 * Statistics dashboard panel
 */
function StatsPanel({ stats }) {
    return (
        <div className="stats-panel">
            <div className="stat-card">
                <div className="stat-value">{stats.total_papers.toLocaleString()}</div>
                <div className="stat-label">Total Papers</div>
            </div>

            <div className="stat-card">
                <div className="stat-value">{stats.papers_last_7_days}</div>
                <div className="stat-label">Added This Week</div>
            </div>

            <div className="stat-card">
                <div className="stat-value">
                    {stats.embeddings_count !== null ? stats.embeddings_count.toLocaleString() : 'N/A'}
                </div>
                <div className="stat-label">
                    Indexed for Search
                    {stats.semantic_search_available && ' ✓'}
                </div>
            </div>

            <div className="stat-card">
                <div className="stat-value">
                    {stats.top_categories?.[0]?.[0]?.split(',')[0] || 'cs.LG'}
                </div>
                <div className="stat-label">Top Category</div>
            </div>
        </div>
    );
}

export default StatsPanel;
