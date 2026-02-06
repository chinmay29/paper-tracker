/**
 * Search bar with mode toggle (keyword vs semantic)
 */
function SearchBar({ query, onQueryChange, mode, onModeChange, isSearching }) {
    return (
        <div className="search-container">
            <div className="search-box">
                <span className="search-icon">🔍</span>
                <input
                    type="text"
                    className="search-input"
                    placeholder="Search research papers by title, abstract, or topic..."
                    value={query}
                    onChange={(e) => onQueryChange(e.target.value)}
                />
                {isSearching && (
                    <span className="spinner" style={{ width: 20, height: 20, borderWidth: 2 }} />
                )}
                <div className="search-mode-toggle">
                    <button
                        className={`search-mode-btn ${mode === 'keyword' ? 'active' : ''}`}
                        onClick={() => onModeChange('keyword')}
                    >
                        Keyword
                    </button>
                    <button
                        className={`search-mode-btn ${mode === 'semantic' ? 'active' : ''}`}
                        onClick={() => onModeChange('semantic')}
                        title="Uses AI embeddings for semantic similarity"
                    >
                        ✨ Semantic
                    </button>
                </div>
            </div>
        </div>
    );
}

export default SearchBar;
