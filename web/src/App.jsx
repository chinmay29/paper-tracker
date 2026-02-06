import { useState, useEffect, useCallback } from 'react';
import { getPapers, searchPapers, getStats, fetchNewPapers, getRankedPapers, scoreAllPapers } from './api/client';
import Header from './components/Header';
import SearchBar from './components/SearchBar';
import StatsPanel from './components/StatsPanel';
import PaperCard from './components/PaperCard';
import PaperDetail from './components/PaperDetail';
import LoadingSpinner from './components/LoadingSpinner';

function App() {
    const [papers, setPapers] = useState([]);
    const [stats, setStats] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [selectedPaper, setSelectedPaper] = useState(null);
    const [searchQuery, setSearchQuery] = useState('');
    const [searchMode, setSearchMode] = useState('keyword');
    const [isSearching, setIsSearching] = useState(false);
    const [fetchingPapers, setFetchingPapers] = useState(false);

    // New state for ranked view
    const [viewMode, setViewMode] = useState('recent'); // 'recent' or 'ranked'
    const [tierFilter, setTierFilter] = useState('');
    const [topicFilter, setTopicFilter] = useState('');
    const [isScoring, setIsScoring] = useState(false);

    // Load initial data
    const loadPapers = useCallback(async () => {
        try {
            setLoading(true);
            let papersData;

            if (viewMode === 'ranked') {
                papersData = await getRankedPapers({
                    limit: 50,
                    tier: tierFilter || undefined,
                    topicCategory: topicFilter || undefined
                });
                // getRankedPapers returns array directly
                setPapers(papersData);
            } else {
                papersData = await getPapers({ limit: 50 });
                setPapers(papersData.papers);
            }

            const statsData = await getStats();
            setStats(statsData);
            setError(null);
        } catch (err) {
            console.error('Failed to load data:', err);
            setError(err.message || 'Failed to load data');
        } finally {
            setLoading(false);
        }
    }, [viewMode, tierFilter, topicFilter]);

    useEffect(() => {
        loadPapers();
    }, [loadPapers]);

    // Search handler
    const handleSearch = useCallback(async (query, mode) => {
        if (!query.trim()) {
            loadPapers();
            return;
        }

        try {
            setIsSearching(true);
            const results = await searchPapers({ query, mode, limit: 50 });
            setPapers(results.papers);
            setError(null);
        } catch (err) {
            console.error('Search failed:', err);
            if (err.status === 503 && mode === 'semantic') {
                setError('Semantic search is not available. Please use keyword search.');
            } else {
                setError(err.message || 'Search failed');
            }
        } finally {
            setIsSearching(false);
        }
    }, [loadPapers]);

    // Debounced search
    useEffect(() => {
        if (viewMode === 'ranked' && searchQuery) {
            // Can't search in ranked mode, switch to recent
            setViewMode('recent');
        }
        const timer = setTimeout(() => {
            handleSearch(searchQuery, searchMode);
        }, 300);
        return () => clearTimeout(timer);
    }, [searchQuery, searchMode, handleSearch, viewMode]);

    // Fetch new papers handler
    const handleFetchPapers = async () => {
        try {
            setFetchingPapers(true);
            await fetchNewPapers({ days: 7, maxResults: 100, enrich: true });
            // Reload data after a short delay
            setTimeout(async () => {
                await loadPapers();
                setFetchingPapers(false);
            }, 2000);
        } catch (err) {
            console.error('Failed to fetch papers:', err);
            setError(err.message);
            setFetchingPapers(false);
        }
    };

    // Score all papers handler
    const handleScoreAll = async () => {
        try {
            setIsScoring(true);
            const result = await scoreAllPapers(200);
            await loadPapers();
            setError(null);
            console.log('Scored papers:', result);
        } catch (err) {
            console.error('Failed to score papers:', err);
            setError(err.message);
        } finally {
            setIsScoring(false);
        }
    };

    return (
        <>
            <Header
                onFetchPapers={handleFetchPapers}
                fetchingPapers={fetchingPapers}
            />

            <main className="main">
                <div className="container">
                    <SearchBar
                        query={searchQuery}
                        onQueryChange={setSearchQuery}
                        mode={searchMode}
                        onModeChange={setSearchMode}
                        isSearching={isSearching}
                    />

                    {/* View Mode Toggle */}
                    <div style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '12px',
                        marginBottom: '1rem',
                        flexWrap: 'wrap'
                    }}>
                        <div style={{
                            display: 'flex',
                            background: 'rgba(30, 41, 59, 0.5)',
                            borderRadius: '8px',
                            padding: '4px',
                            border: '1px solid rgba(148, 163, 184, 0.1)'
                        }}>
                            <button
                                onClick={() => setViewMode('recent')}
                                style={{
                                    padding: '8px 16px',
                                    border: 'none',
                                    borderRadius: '6px',
                                    cursor: 'pointer',
                                    fontWeight: '500',
                                    fontSize: '14px',
                                    transition: 'all 0.2s',
                                    background: viewMode === 'recent'
                                        ? 'linear-gradient(135deg, #3b82f6, #2563eb)'
                                        : 'transparent',
                                    color: viewMode === 'recent' ? '#fff' : '#94a3b8'
                                }}
                            >
                                📅 Recent
                            </button>
                            <button
                                onClick={() => setViewMode('ranked')}
                                style={{
                                    padding: '8px 16px',
                                    border: 'none',
                                    borderRadius: '6px',
                                    cursor: 'pointer',
                                    fontWeight: '500',
                                    fontSize: '14px',
                                    transition: 'all 0.2s',
                                    background: viewMode === 'ranked'
                                        ? 'linear-gradient(135deg, #a855f7, #7c3aed)'
                                        : 'transparent',
                                    color: viewMode === 'ranked' ? '#fff' : '#94a3b8'
                                }}
                            >
                                ⭐ Ranked
                            </button>
                        </div>

                        {viewMode === 'ranked' && (
                            <>
                                <select
                                    value={tierFilter}
                                    onChange={(e) => setTierFilter(e.target.value)}
                                    style={{
                                        padding: '8px 12px',
                                        background: 'rgba(30, 41, 59, 0.5)',
                                        border: '1px solid rgba(148, 163, 184, 0.2)',
                                        borderRadius: '8px',
                                        color: '#e2e8f0',
                                        fontSize: '14px',
                                        cursor: 'pointer'
                                    }}
                                >
                                    <option value="">All Tiers</option>
                                    <option value="S">🏆 S Tier</option>
                                    <option value="A">🥇 A Tier</option>
                                    <option value="B">🥈 B Tier</option>
                                    <option value="C">🥉 C Tier</option>
                                    <option value="D">📌 D Tier</option>
                                </select>
                                <select
                                    value={topicFilter}
                                    onChange={(e) => setTopicFilter(e.target.value)}
                                    style={{
                                        padding: '8px 12px',
                                        background: 'rgba(30, 41, 59, 0.5)',
                                        border: '1px solid rgba(148, 163, 184, 0.2)',
                                        borderRadius: '8px',
                                        color: '#e2e8f0',
                                        fontSize: '14px',
                                        cursor: 'pointer'
                                    }}
                                >
                                    <option value="">All Topics</option>
                                    <option value="quantization">🔢 Quantization</option>
                                    <option value="kv_cache">💾 KV Cache</option>
                                    <option value="speculative_decoding">⚡ Speculative Decoding</option>
                                    <option value="batching">📦 Batching</option>
                                    <option value="parallelism">🔀 Parallelism</option>
                                    <option value="memory_optimization">🧠 Memory</option>
                                    <option value="serving">🖥️ Serving</option>
                                    <option value="efficiency">⚙️ Efficiency</option>
                                </select>
                            </>
                        )}

                        <button
                            onClick={handleScoreAll}
                            disabled={isScoring}
                            style={{
                                padding: '8px 16px',
                                background: isScoring
                                    ? 'rgba(100, 116, 139, 0.3)'
                                    : 'linear-gradient(135deg, #22c55e, #16a34a)',
                                border: 'none',
                                borderRadius: '8px',
                                color: '#fff',
                                fontWeight: '500',
                                fontSize: '14px',
                                cursor: isScoring ? 'not-allowed' : 'pointer',
                                marginLeft: 'auto'
                            }}
                        >
                            {isScoring ? '⏳ Scoring...' : '🎯 Score All Papers'}
                        </button>
                    </div>

                    {stats && <StatsPanel stats={stats} />}

                    {error && (
                        <div className="error-banner" style={{
                            padding: '1rem',
                            marginBottom: '1rem',
                            background: 'rgba(239, 68, 68, 0.1)',
                            border: '1px solid rgba(239, 68, 68, 0.3)',
                            borderRadius: '0.75rem',
                            color: '#ef4444'
                        }}>
                            {error}
                        </div>
                    )}

                    {loading ? (
                        <LoadingSpinner text="Loading papers..." />
                    ) : papers.length === 0 ? (
                        <div className="empty-state">
                            <div className="empty-icon">📚</div>
                            <h3 className="empty-title">No papers found</h3>
                            <p className="empty-description">
                                {searchQuery
                                    ? `No results for "${searchQuery}". Try a different search term.`
                                    : viewMode === 'ranked'
                                        ? 'No scored papers yet. Click "Score All Papers" to score them.'
                                        : 'Click "Fetch Papers" to get the latest research papers.'}
                            </p>
                        </div>
                    ) : (
                        <div className="papers-grid">
                            {papers.map((paper) => (
                                <PaperCard
                                    key={paper.arxiv_id}
                                    paper={paper}
                                    onClick={() => setSelectedPaper(paper)}
                                />
                            ))}
                        </div>
                    )}
                </div>
            </main>

            {selectedPaper && (
                <PaperDetail
                    paper={selectedPaper}
                    onClose={() => setSelectedPaper(null)}
                />
            )}
        </>
    );
}

export default App;

