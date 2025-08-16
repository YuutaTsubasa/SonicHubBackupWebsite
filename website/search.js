// Search functionality for SonicHub backup website
class SonicHubSearch {
    constructor() {
        this.index = null;
        this.isLoading = false;
    }

    async loadIndex() {
        if (this.index || this.isLoading) return;
        
        this.isLoading = true;
        try {
            const response = await fetch('search_index.json');
            this.index = await response.json();
            console.log(`Search index loaded: ${Object.keys(this.index.threads).length} threads, ${Object.keys(this.index.forums).length} forums`);
        } catch (error) {
            console.error('Failed to load search index:', error);
        }
        this.isLoading = false;
    }

    normalizeText(text) {
        if (!text) return '';
        return text.toLowerCase()
            .replace(/[^\w\u4e00-\u9fff\s]/g, '') // Keep only letters, numbers, Chinese characters, and spaces
            .trim();
    }

    searchInText(text, keywords) {
        const normalizedText = this.normalizeText(text);
        return keywords.some(keyword => normalizedText.includes(keyword));
    }

    async search(query, options = {}) {
        await this.loadIndex();
        if (!this.index || !query.trim()) return [];

        const {
            searchAuthor = true,
            searchTitle = true,
            searchContent = true,
            maxResults = 50
        } = options;

        const keywords = this.normalizeText(query).split(/\s+/).filter(k => k.length > 0);
        if (keywords.length === 0) return [];

        const results = [];

        // Search through threads
        for (const [filename, thread] of Object.entries(this.index.threads)) {
            let matches = [];
            
            // Search in thread title
            if (searchTitle && this.searchInText(thread.title, keywords)) {
                matches.push({ type: 'title', text: thread.title });
            }

            // Search in posts
            for (let i = 0; i < thread.posts.length; i++) {
                const post = thread.posts[i];
                let postMatches = [];

                // Search in author
                if (searchAuthor && this.searchInText(post.author, keywords)) {
                    postMatches.push({ type: 'author', text: post.author });
                }

                // Search in content
                if (searchContent && this.searchInText(post.content, keywords)) {
                    postMatches.push({ type: 'content', text: post.content.substring(0, 200) + '...' });
                }

                if (postMatches.length > 0) {
                    matches.push({
                        type: 'post',
                        postIndex: i,
                        author: post.author,
                        date: post.date,
                        matches: postMatches
                    });
                }
            }

            if (matches.length > 0) {
                results.push({
                    type: 'thread',
                    file: filename,
                    title: thread.title,
                    matches: matches,
                    score: matches.length // Simple scoring by number of matches
                });
            }
        }

        // Sort by relevance (score) and limit results
        results.sort((a, b) => b.score - a.score);
        return results.slice(0, maxResults);
    }

    formatSearchResults(results) {
        if (results.length === 0) {
            return '<div class="search-no-results">找不到符合的搜尋結果。</div>';
        }

        let html = `<div class="search-results-header">找到 ${results.length} 個相關結果：</div>`;
        
        for (const result of results) {
            html += `
                <div class="search-result-item">
                    <div class="search-result-title">
                        <a href="${result.file}" target="_blank">${this.escapeHtml(result.title)}</a>
                    </div>
                    <div class="search-result-matches">`;
            
            for (const match of result.matches) {
                if (match.type === 'title') {
                    html += `<div class="search-match search-match-title">📋 標題符合: ${this.escapeHtml(match.text)}</div>`;
                } else if (match.type === 'post') {
                    html += `<div class="search-match search-match-post">
                        <div class="search-post-info">👤 ${this.escapeHtml(match.author)} | 🕐 ${match.date}</div>`;
                    
                    for (const postMatch of match.matches) {
                        if (postMatch.type === 'author') {
                            html += `<div class="search-post-match">👤 作者符合: ${this.escapeHtml(postMatch.text)}</div>`;
                        } else if (postMatch.type === 'content') {
                            html += `<div class="search-post-match">📝 內容符合: ${this.escapeHtml(postMatch.text)}</div>`;
                        }
                    }
                    html += `</div>`;
                }
            }
            
            html += `</div>
                </div>`;
        }

        return html;
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Initialize search functionality when DOM is loaded
let sonicHubSearch;

document.addEventListener('DOMContentLoaded', function() {
    sonicHubSearch = new SonicHubSearch();
    
    const searchForm = document.getElementById('search-form');
    const searchInput = document.getElementById('search-input');
    const searchResults = document.getElementById('search-results');
    const searchLoading = document.getElementById('search-loading');

    if (searchForm && searchInput && searchResults) {
        searchForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            await performSearch();
        });

        searchInput.addEventListener('input', debounce(async function() {
            if (searchInput.value.trim().length >= 2) {
                await performSearch();
            } else {
                searchResults.innerHTML = '';
                searchResults.style.display = 'none';
            }
        }, 500));
    }

    async function performSearch() {
        const query = searchInput.value.trim();
        if (!query) {
            searchResults.innerHTML = '';
            searchResults.style.display = 'none';
            return;
        }

        // Show loading indicator
        searchLoading.style.display = 'block';
        searchResults.style.display = 'none';

        try {
            const results = await sonicHubSearch.search(query);
            const resultsHtml = sonicHubSearch.formatSearchResults(results);
            
            searchResults.innerHTML = resultsHtml;
            searchResults.style.display = 'block';
        } catch (error) {
            console.error('Search error:', error);
            searchResults.innerHTML = '<div class="search-error">搜尋時發生錯誤，請稍後再試。</div>';
            searchResults.style.display = 'block';
        }

        searchLoading.style.display = 'none';
    }

    // Debounce function to limit search frequency
    function debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }
});