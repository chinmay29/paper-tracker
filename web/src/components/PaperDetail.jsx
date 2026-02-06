import { useEffect } from 'react';

/**
 * Paper detail modal - shows full paper information
 */
function PaperDetail({ paper, onClose }) {
    const formatDate = (isoString) => {
        const date = new Date(isoString);
        return date.toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'long',
            day: 'numeric',
        });
    };

    // Close on escape key
    useEffect(() => {
        const handleEscape = (e) => {
            if (e.key === 'Escape') onClose();
        };
        document.addEventListener('keydown', handleEscape);
        return () => document.removeEventListener('keydown', handleEscape);
    }, [onClose]);

    // Prevent body scroll when modal is open
    useEffect(() => {
        document.body.style.overflow = 'hidden';
        return () => {
            document.body.style.overflow = '';
        };
    }, []);

    return (
        <div className="modal-overlay" onClick={onClose}>
            <div className="modal-content" onClick={(e) => e.stopPropagation()}>
                <div className="modal-header">
                    <div>
                        <h2 style={{ marginBottom: '0.5rem' }}>{paper.title}</h2>
                        <div className="paper-meta">
                            <span className="paper-tag category">{paper.primary_category}</span>
                            <span className="paper-tag date">📅 {formatDate(paper.published)}</span>
                            {paper.citation_count > 0 && (
                                <span className="paper-tag citations">
                                    📊 {paper.citation_count} citations
                                    {paper.influential_citation_count > 0 &&
                                        ` (${paper.influential_citation_count} influential)`}
                                </span>
                            )}
                        </div>
                    </div>
                    <button className="modal-close" onClick={onClose}>
                        ✕
                    </button>
                </div>

                <div className="modal-body">
                    <div className="modal-section">
                        <h4 className="modal-section-title">Authors</h4>
                        <p style={{ color: 'var(--text-primary)' }}>
                            {paper.authors ? paper.authors.join(', ') : paper.authors_str || 'Unknown'}
                        </p>
                    </div>

                    <div className="modal-section">
                        <h4 className="modal-section-title">Abstract</h4>
                        <p className="modal-abstract">{paper.abstract}</p>
                    </div>

                    <div className="modal-section">
                        <h4 className="modal-section-title">Categories</h4>
                        <div className="paper-meta">
                            {(paper.categories || [paper.primary_category] || []).filter(Boolean).map((cat, idx) => (
                                <span key={`${cat}-${idx}`} className="paper-tag category">{cat}</span>
                            ))}
                        </div>
                    </div>

                    {(paper.venue || paper.has_code) && (
                        <div className="modal-section">
                            <h4 className="modal-section-title">Additional Info</h4>
                            {paper.venue && (
                                <p style={{ marginBottom: '0.5rem' }}>
                                    <strong>Venue:</strong> {paper.venue}
                                </p>
                            )}
                            {paper.has_code && paper.github_url && (
                                <p>
                                    <strong>Code:</strong>{' '}
                                    <a href={paper.github_url} target="_blank" rel="noopener noreferrer">
                                        {paper.github_url}
                                    </a>
                                </p>
                            )}
                        </div>
                    )}

                    <div className="modal-section">
                        <h4 className="modal-section-title">Links</h4>
                        <div style={{ display: 'flex', gap: '0.75rem' }}>
                            <a
                                href={paper.pdf_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="btn btn-primary"
                            >
                                📄 View PDF
                            </a>
                            <a
                                href={paper.arxiv_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="btn btn-secondary"
                            >
                                🔗 Open on arXiv
                            </a>
                            {paper.github_url && (
                                <a
                                    href={paper.github_url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="btn btn-secondary"
                                >
                                    💻 View Code
                                </a>
                            )}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}

export default PaperDetail;
