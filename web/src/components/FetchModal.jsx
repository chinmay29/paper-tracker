import { useState, useEffect } from 'react';
import { getFetchKeywords, fetchNewPapers } from '../api/client';

/**
 * Modal for fetching papers with keyword selection
 */
function FetchModal({ isOpen, onClose, onFetchComplete }) {
    const [keywords, setKeywords] = useState([]);
    const [selectedKeywords, setSelectedKeywords] = useState([]);
    const [customKeyword, setCustomKeyword] = useState('');
    const [days, setDays] = useState(7);
    const [maxResults, setMaxResults] = useState(100);
    const [loading, setLoading] = useState(false);
    const [fetching, setFetching] = useState(false);

    useEffect(() => {
        if (isOpen) {
            loadKeywords();
        }
    }, [isOpen]);

    const loadKeywords = async () => {
        try {
            setLoading(true);
            const data = await getFetchKeywords();
            setKeywords(data.default || []);
            setSelectedKeywords(data.default || []);
        } catch (err) {
            console.error('Failed to load keywords:', err);
            // Fallback to hardcoded
            const fallback = ['inference', 'LLM', 'quantization', 'serving', 'optimization'];
            setKeywords(fallback);
            setSelectedKeywords(fallback);
        } finally {
            setLoading(false);
        }
    };

    const toggleKeyword = (keyword) => {
        setSelectedKeywords(prev =>
            prev.includes(keyword)
                ? prev.filter(k => k !== keyword)
                : [...prev, keyword]
        );
    };

    const selectAll = () => setSelectedKeywords([...keywords]);
    const clearAll = () => setSelectedKeywords([]);

    const addCustomKeyword = () => {
        const trimmed = customKeyword.trim();
        if (trimmed && !selectedKeywords.includes(trimmed)) {
            setSelectedKeywords(prev => [...prev, trimmed]);
            if (!keywords.includes(trimmed)) {
                setKeywords(prev => [...prev, trimmed]);
            }
        }
        setCustomKeyword('');
    };

    const handleKeyPress = (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            addCustomKeyword();
        }
    };

    const handleFetch = async () => {
        try {
            setFetching(true);
            await fetchNewPapers({
                days,
                maxResults,
                enrich: true,
                keywords: selectedKeywords.length > 0 ? selectedKeywords : null,
            });
            onFetchComplete?.();
            onClose();
        } catch (err) {
            console.error('Failed to fetch papers:', err);
        } finally {
            setFetching(false);
        }
    };

    if (!isOpen) return null;

    return (
        <div className="modal-overlay" onClick={onClose}>
            <div
                className="modal-content"
                onClick={(e) => e.stopPropagation()}
                style={{ maxWidth: '600px' }}
            >
                <div className="modal-header">
                    <h2 style={{ marginBottom: '0.5rem' }}>🔍 Fetch Papers from arXiv</h2>
                    <button className="modal-close" onClick={onClose}>✕</button>
                </div>

                <div className="modal-body">
                    {/* Options */}
                    <div style={{ display: 'flex', gap: '1rem', marginBottom: '1.5rem' }}>
                        <div>
                            <label style={{ color: '#94a3b8', fontSize: '12px', display: 'block', marginBottom: '4px' }}>
                                Days Back
                            </label>
                            <select
                                value={days}
                                onChange={(e) => setDays(Number(e.target.value))}
                                style={{
                                    padding: '8px 12px',
                                    background: 'rgba(30, 41, 59, 0.5)',
                                    border: '1px solid rgba(148, 163, 184, 0.2)',
                                    borderRadius: '6px',
                                    color: '#e2e8f0',
                                }}
                            >
                                <option value={3}>3 days</option>
                                <option value={7}>7 days</option>
                                <option value={14}>14 days</option>
                                <option value={30}>30 days</option>
                            </select>
                        </div>
                        <div>
                            <label style={{ color: '#94a3b8', fontSize: '12px', display: 'block', marginBottom: '4px' }}>
                                Max Results
                            </label>
                            <select
                                value={maxResults}
                                onChange={(e) => setMaxResults(Number(e.target.value))}
                                style={{
                                    padding: '8px 12px',
                                    background: 'rgba(30, 41, 59, 0.5)',
                                    border: '1px solid rgba(148, 163, 184, 0.2)',
                                    borderRadius: '6px',
                                    color: '#e2e8f0',
                                }}
                            >
                                <option value={50}>50</option>
                                <option value={100}>100</option>
                                <option value={200}>200</option>
                            </select>
                        </div>
                    </div>

                    {/* Keywords */}
                    <div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
                            <label style={{ color: '#94a3b8', fontSize: '14px', fontWeight: '500' }}>
                                Keywords to Search ({selectedKeywords.length} selected)
                            </label>
                            <div style={{ display: 'flex', gap: '8px' }}>
                                <button
                                    onClick={selectAll}
                                    style={{
                                        padding: '4px 8px',
                                        background: 'transparent',
                                        border: '1px solid rgba(148, 163, 184, 0.3)',
                                        borderRadius: '4px',
                                        color: '#94a3b8',
                                        fontSize: '12px',
                                        cursor: 'pointer',
                                    }}
                                >
                                    Select All
                                </button>
                                <button
                                    onClick={clearAll}
                                    style={{
                                        padding: '4px 8px',
                                        background: 'transparent',
                                        border: '1px solid rgba(148, 163, 184, 0.3)',
                                        borderRadius: '4px',
                                        color: '#94a3b8',
                                        fontSize: '12px',
                                        cursor: 'pointer',
                                    }}
                                >
                                    Clear
                                </button>
                            </div>
                        </div>

                        {/* Custom keyword input */}
                        <div style={{ display: 'flex', gap: '8px', marginBottom: '12px' }}>
                            <input
                                type="text"
                                value={customKeyword}
                                onChange={(e) => setCustomKeyword(e.target.value)}
                                onKeyPress={handleKeyPress}
                                placeholder="Add custom keyword..."
                                style={{
                                    flex: 1,
                                    padding: '8px 12px',
                                    background: 'rgba(30, 41, 59, 0.5)',
                                    border: '1px solid rgba(148, 163, 184, 0.2)',
                                    borderRadius: '6px',
                                    color: '#e2e8f0',
                                    fontSize: '14px',
                                }}
                            />
                            <button
                                onClick={addCustomKeyword}
                                disabled={!customKeyword.trim()}
                                style={{
                                    padding: '8px 16px',
                                    background: customKeyword.trim() ? 'linear-gradient(135deg, #8b5cf6, #7c3aed)' : 'rgba(100, 116, 139, 0.3)',
                                    border: 'none',
                                    borderRadius: '6px',
                                    color: '#fff',
                                    fontWeight: '500',
                                    cursor: customKeyword.trim() ? 'pointer' : 'not-allowed',
                                }}
                            >
                                + Add
                            </button>
                        </div>

                        {loading ? (
                            <div style={{ color: '#94a3b8', padding: '1rem' }}>Loading keywords...</div>
                        ) : (
                            <div style={{
                                display: 'flex',
                                flexWrap: 'wrap',
                                gap: '8px',
                                maxHeight: '200px',
                                overflowY: 'auto',
                                padding: '8px',
                                background: 'rgba(15, 23, 42, 0.5)',
                                borderRadius: '8px',
                                border: '1px solid rgba(148, 163, 184, 0.1)',
                            }}>
                                {keywords.map((keyword) => (
                                    <button
                                        key={keyword}
                                        onClick={() => toggleKeyword(keyword)}
                                        style={{
                                            padding: '6px 12px',
                                            background: selectedKeywords.includes(keyword)
                                                ? 'linear-gradient(135deg, #3b82f6, #2563eb)'
                                                : 'rgba(51, 65, 85, 0.5)',
                                            border: 'none',
                                            borderRadius: '16px',
                                            color: selectedKeywords.includes(keyword) ? '#fff' : '#94a3b8',
                                            fontSize: '13px',
                                            cursor: 'pointer',
                                            transition: 'all 0.2s',
                                        }}
                                    >
                                        {selectedKeywords.includes(keyword) ? '✓ ' : ''}{keyword}
                                    </button>
                                ))}
                            </div>
                        )}
                    </div>

                    {/* Actions */}
                    <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', marginTop: '1.5rem' }}>
                        <button
                            onClick={onClose}
                            style={{
                                padding: '10px 20px',
                                background: 'rgba(100, 116, 139, 0.3)',
                                border: 'none',
                                borderRadius: '8px',
                                color: '#e2e8f0',
                                fontWeight: '500',
                                cursor: 'pointer',
                            }}
                        >
                            Cancel
                        </button>
                        <button
                            onClick={handleFetch}
                            disabled={fetching || selectedKeywords.length === 0}
                            style={{
                                padding: '10px 20px',
                                background: fetching || selectedKeywords.length === 0
                                    ? 'rgba(100, 116, 139, 0.3)'
                                    : 'linear-gradient(135deg, #22c55e, #16a34a)',
                                border: 'none',
                                borderRadius: '8px',
                                color: '#fff',
                                fontWeight: '500',
                                cursor: fetching || selectedKeywords.length === 0 ? 'not-allowed' : 'pointer',
                            }}
                        >
                            {fetching ? '⏳ Fetching...' : '🚀 Fetch Papers'}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}

export default FetchModal;
