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
        let message = data.detail || `HTTP ${response.status}`;

        // Handle FastAPI validation error structure
        if (Array.isArray(data.detail)) {
            message = data.detail.map(e => `${e.loc.join('.')}: ${e.msg}`).join(', ');
        } else if (typeof message === 'object') {
            message = JSON.stringify(message);
        }

        throw new ApiError(
            message,
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
export async function fetchNewPapers({ days = 7, maxResults = 100, enrich = false, keywords = null } = {}) {
    return fetchApi('/fetch', {
        method: 'POST',
        body: JSON.stringify({
            days,
            max_results: maxResults,
            enrich,
            keywords,
        }),
    });
}

/**
 * Get available fetch keywords
 */
export async function getFetchKeywords() {
    return fetchApi('/fetch-keywords');
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

/**
 * Get ranked papers with scores
 */
export async function getRankedPapers({ limit = 20, page = 1, minScore, tier, topicCategory } = {}) {
    const params = new URLSearchParams({ limit, page });
    if (minScore) params.set('min_score', minScore);
    if (tier) params.set('tier', tier);
    if (topicCategory) params.set('topic_category', topicCategory);
    return fetchApi(`/ranked-papers?${params}`);
}

/**
 * Score a single paper
 */
export async function scorePaper(arxivId) {
    return fetchApi(`/score/${encodeURIComponent(arxivId)}`, { method: 'POST' });
}

/**
 * Score all unscored papers
 */
export async function scoreAllPapers({ limit = 100, usePdf = false, rescoreAll = false } = {}) {
    const params = new URLSearchParams({ limit });
    if (usePdf) params.set('use_pdf', 'true');
    if (rescoreAll) params.set('rescore_all', 'true');
    return fetchApi(`/score-all?${params}`, { method: 'POST' });
}

/**
 * Get paper score breakdown
 */
export async function getPaperScore(arxivId) {
    return fetchApi(`/paper/${encodeURIComponent(arxivId)}/score`);
}

/**
 * Get current background task status
 */
export async function getTaskStatus() {
    return fetchApi('/task-status');
}

/**
 * Get topic categories
 */
export async function getTopicCategories() {
    return fetchApi('/topic-categories');
}

export { ApiError };

