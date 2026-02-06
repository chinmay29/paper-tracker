/**
 * Paper card component for list view
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

    return (
        <article className="paper-card" onClick={onClick}>
            <div className="paper-header">
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
