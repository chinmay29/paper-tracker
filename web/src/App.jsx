import { useState, useEffect, useCallback } from 'react';
import { getPapers, searchPapers, getStats, fetchNewPapers, getRankedPapers, scoreAllPapers } from './api/client';
import Header from './components/Header';
import SearchBar from './components/SearchBar';
import StatsPanel from './components/StatsPanel';
import PaperCard from './components/PaperCard';
import PaperDetail from './components/PaperDetail';
import LoadingSpinner from './components/LoadingSpinner';
import FetchModal from './components/FetchModal';
import { useToast } from './components/Toast';

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
    const [showFetchModal, setShowFetchModal] = useState(false);

    // Toast for progress notifications
    const { showToast, updateProgress, hideToast, ToastComponent } = useToast();

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

    // Poll for stats updates
    const startPolling = useCallback(async (initialStats, targetCount, type = 'scoring') => {
        const startTime = Date.now();
        const pollInterval = setInterval(async () => {
            try {
                const newStats = await getStats();
                setStats(newStats);

                let progress = 0;
                let done = false;

                if (type === 'scoring') {
                    const scored = newStats.scored_papers - initialStats.scored_papers;
                    progress = Math.min(100, (scored / targetCount) * 100);
                    updateProgress(progress, `Scoring papers: ${scored} / ${targetCount}`);

                    if (scored >= targetCount) done = true;
                } else if (type === 'fetching') {
                    const fetched = newStats.total_papers - initialStats.total_papers;
                    // Indeterminate progress for fetching since we don't look total
                    updateProgress(null, `Fetched ${fetched} new papers...`);

                    // Stop after 30s or if papers stop increasing for 5s (simplified: just 30s timeout or manual reload)
                    // For now, let's just run for 5s then reload papers to see if any
                    // Actually, let's just trigger a reload every few seconds
                    if (fetched > 0) loadPapers();
                }

                if (done || Date.now() - startTime > 300000) { // 5 min timeout
                    clearInterval(pollInterval);
                    if (done) {
                        showToast('Task completed successfully!', 'success', null, 3000);
                        setTimeout(loadPapers, 1000);
                        setIsScoring(false);
                        setFetchingPapers(false);
                    } else {
                        showToast('Task taking longer than expected. check back later.', 'warning', null, 5000);
                        setIsScoring(false);
                        setFetchingPapers(false);
                    }
                }
            } catch (err) {
                console.error('Polling error:', err);
            }
        }, 2000);

        return pollInterval;
    }, [updateProgress, loadPapers, showToast]);

    // Handle fetch modal completion
    const handleFetchStart = async () => {
        setFetchingPapers(true);
        const currentStats = await getStats();
        showToast('Fetching papers from arXiv...', 'info');

        // Simple polling for a while to update stats
        // fetching is fast, usually 10-20s.
        startPolling(currentStats, 100, 'fetching');

        // Timeout to stop "fetching" state visually after 20s if not done
        setTimeout(() => {
            setFetchingPapers(false);
            loadPapers();
            hideToast();
        }, 20000);
    };

    // Score all papers handler
    const handleScoreAll = async (usePdf = false, rescoreAll = false) => {
        try {
            setIsScoring(true);
            const currentStats = await getStats();

            showToast('Starting scoring...', 'info', 0);

            const result = await scoreAllPapers({ limit: 200, usePdf, rescoreAll });
            const queuedCount = result.scored;

            if (queuedCount === 0) {
                showToast('No papers to score!', 'success', null, 3000);
                setIsScoring(false);
                return;
            }

            console.log(`Queued ${queuedCount} papers for scoring`);
            startPolling(currentStats, queuedCount, 'scoring');

        } catch (err) {
            console.error('Failed to score papers:', err);
            setError(err.message);
            setIsScoring(false);
            showToast(`Error: ${err.message}`, 'error', null, 5000);
        }
    };

    return (
        <>
            <Header
                onFetchPapers={() => setShowFetchModal(true)}
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
                            onClick={() => handleScoreAll(false, false)}
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
                            {isScoring ? '⏳ Scoring...' : '🎯 Score New'}
                        </button>
                        <button
                            onClick={() => handleScoreAll(true, true)}
                            disabled={isScoring}
                            title="Re-score all papers using full PDF text (slower but more accurate)"
                            style={{
                                padding: '8px 16px',
                                background: isScoring
                                    ? 'rgba(100, 116, 139, 0.3)'
                                    : 'linear-gradient(135deg, #f59e0b, #d97706)',
                                border: 'none',
                                borderRadius: '8px',
                                color: '#fff',
                                fontWeight: '500',
                                fontSize: '14px',
                                cursor: isScoring ? 'not-allowed' : 'pointer',
                            }}
                        >
                            {isScoring ? '⏳ Processing...' : '📄 Re-score with PDF'}
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

            <FetchModal
                isOpen={showFetchModal}
                onClose={() => setShowFetchModal(false)}
                onFetchComplete={handleFetchStart}
            />

            {ToastComponent}
        </>
    );
}

export default App;
