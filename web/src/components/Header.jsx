/**
 * Header component with logo and actions
 */
function Header({ onFetchPapers, fetchingPapers }) {
    return (
        <header className="header">
            <div className="container header-content">
                <div className="logo">
                    <span className="logo-icon">📄</span>
                    <span>Paper Tracker</span>
                </div>

                <div className="header-actions">
                    <button
                        className="btn btn-primary"
                        onClick={onFetchPapers}
                        disabled={fetchingPapers}
                    >
                        {fetchingPapers ? (
                            <>
                                <span className="spinner" style={{ width: 16, height: 16, borderWidth: 2 }} />
                                Fetching...
                            </>
                        ) : (
                            <>
                                <span>🔄</span>
                                Fetch Papers
                            </>
                        )}
                    </button>
                </div>
            </div>
        </header>
    );
}

export default Header;
