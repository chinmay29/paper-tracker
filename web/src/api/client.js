/**
 * API client for Paper Tracker backend
 */

const API_BASE = '/api';

class ApiError extends Error {
    constructor(message, status, data) {
        super(message);
        this.status = status;
        this.data = data;
    }
}

async function fetchApi(endpoint, options = {}) {
    const url = `${API_BASE}${endpoint}`;

    const response = await fetch(url, {
        headers: {
            'Content-Type': 'application/json',
            ...options.headers,
        },
        ...options,
    });

    if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new ApiError(
            data.detail || `HTTP ${response.status}`,
            response.status,
            data
        );
    }

    return response.json();
}

/**
 * Get list of papers with pagination
 */
export async function getPapers({ limit = 20, page = 1, days, category, sortBy = 'published' } = {}) {
    const params = new URLSearchParams({ limit, page, sort_by: sortBy });
    if (days) params.set('days', days);
    if (category) params.set('category', category);

    return fetchApi(`/papers?${params}`);
}

/**
 * Get a single paper by arXiv ID
 */
export async function getPaper(arxivId) {
    return fetchApi(`/papers/${encodeURIComponent(arxivId)}`);
}

/**
 * Search papers by keyword or semantic similarity
 */
export async function searchPapers({ query, mode = 'keyword', limit = 20 }) {
    const params = new URLSearchParams({ q: query, mode, limit });
    return fetchApi(`/search?${params}`);
}

/**
 * Get database statistics
 */
export async function getStats() {
    return fetchApi('/stats');
}

/**
 * Trigger fetching new papers from arXiv
 */
export async function fetchNewPapers({ days = 7, maxResults = 100, enrich = false } = {}) {
    return fetchApi('/fetch', {
        method: 'POST',
        body: JSON.stringify({
            days,
            max_results: maxResults,
            enrich,
        }),
    });
}

/**
 * Sync embeddings from database
 */
export async function syncEmbeddings() {
    return fetchApi('/sync-embeddings', { method: 'POST' });
}

/**
 * Health check
 */
export async function healthCheck() {
    return fetchApi('/health');
}

export { ApiError };
