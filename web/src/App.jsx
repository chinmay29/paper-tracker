import { useState, useEffect, useCallback } from 'react';
import { getPapers, searchPapers, getStats, fetchNewPapers } from './api/client';
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

    // Load initial data
    useEffect(() => {
        async function loadInitialData() {
            try {
                setLoading(true);
                const [papersData, statsData] = await Promise.all([
                    getPapers({ limit: 50 }),
                    getStats(),
                ]);
                setPapers(papersData.papers);
                setStats(statsData);
                setError(null);
            } catch (err) {
                console.error('Failed to load data:', err);
                setError(err.message || 'Failed to load data');
            } finally {
                setLoading(false);
            }
        }
        loadInitialData();
    }, []);

    // Search handler
    const handleSearch = useCallback(async (query, mode) => {
        if (!query.trim()) {
            // Reset to full list
            try {
                setIsSearching(true);
                const papersData = await getPapers({ limit: 50 });
                setPapers(papersData.papers);
            } catch (err) {
                setError(err.message);
            } finally {
                setIsSearching(false);
            }
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
    }, []);

    // Debounced search
    useEffect(() => {
        const timer = setTimeout(() => {
            handleSearch(searchQuery, searchMode);
        }, 300);
        return () => clearTimeout(timer);
    }, [searchQuery, searchMode, handleSearch]);

    // Fetch new papers handler
    const handleFetchPapers = async () => {
        try {
            setFetchingPapers(true);
            await fetchNewPapers({ days: 7, maxResults: 100, enrich: true });
            // Reload data after a short delay
            setTimeout(async () => {
                const [papersData, statsData] = await Promise.all([
                    getPapers({ limit: 50 }),
                    getStats(),
                ]);
                setPapers(papersData.papers);
                setStats(statsData);
                setFetchingPapers(false);
            }, 2000);
        } catch (err) {
            console.error('Failed to fetch papers:', err);
            setError(err.message);
            setFetchingPapers(false);
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
