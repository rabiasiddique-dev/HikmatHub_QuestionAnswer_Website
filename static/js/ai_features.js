document.addEventListener('DOMContentLoaded', function () {
    // Smart Tag Suggestions
    const titleInput = document.getElementById('title');
    const tagsInput = document.getElementById('tags');
    const suggestionsContainer = document.getElementById('suggested-tags-container');
    const suggestionsList = document.getElementById('suggested-tags-list');

    // Check if we are on the ask question page
    if (titleInput && tagsInput && suggestionsContainer) {
        let timeout = null;

        // Listen for input on title and body (if body is a textarea)
        // Note: Body might be managed by EasyMDE, so listening to body change might be tricky directly.
        // We'll trust title predominantly, or listen to main textarea if EasyMDE updates it.
        const bodyInput = document.getElementById('body');

        const fetchSuggestions = () => {
            const title = titleInput.value.trim();
            const body = bodyInput ? bodyInput.value.trim() : '';

            if (title.length < 5 && body.length < 10) {
                suggestionsContainer.style.display = 'none';
                return;
            }

            // Show loading state? nah, just wait

            fetch('/api/suggest-tags', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ title: title, body: body })
            })
                .then(response => response.json())
                .then(data => {
                    if (data.suggested_tags && data.suggested_tags.length > 0) {
                        // Filter out already selected tags
                        const currentTags = tagsInput.value.split(',').map(t => t.trim().toLowerCase());
                        const newSuggestions = data.suggested_tags.filter(tag => !currentTags.includes(tag.toLowerCase()));

                        if (newSuggestions.length > 0) {
                            renderSuggestions(newSuggestions);
                        } else {
                            suggestionsContainer.style.display = 'none';
                        }
                    } else {
                        suggestionsContainer.style.display = 'none';
                    }
                })
                .catch(err => console.error('Error fetching tags:', err));
        };

        const renderSuggestions = (tags) => {
            suggestionsList.innerHTML = '';
            tags.forEach(tag => {
                const badge = document.createElement('span');
                badge.className = 'badge bg-light text-primary border cursor-pointer suggestion-tag';
                badge.style.cursor = 'pointer';
                badge.innerHTML = `<i class="fas fa-plus-circle small"></i> ${tag}`;
                badge.onclick = () => addTag(tag);
                suggestionsList.appendChild(badge);
            });
            suggestionsContainer.style.display = 'block';
        };

        const addTag = (tag) => {
            let currentVal = tagsInput.value.trim();
            if (currentVal && !currentVal.endsWith(',')) {
                currentVal += ', ';
            }
            tagsInput.value = currentVal + tag;

            // Remove from suggestions
            // Re-run fetch or just hide? Just hide for now to keep it simple or re-filter
            fetchSuggestions();
        };

        // Debounce input
        const handleInput = () => {
            clearTimeout(timeout);
            timeout = setTimeout(() => {
                fetchSuggestions();
                fetchSimilarQuestions();
                analyzeQuality();
            }, 1000); // 1-second debounce
        };

        // Similar Questions Logic
        const similarContainer = document.getElementById('similar-questions-container');
        const similarList = document.getElementById('similar-questions-list');

        const fetchSimilarQuestions = () => {
            const title = titleInput.value.trim();
            const body = bodyInput ? bodyInput.value.trim() : '';

            if (title.length < 5) {
                similarContainer.style.display = 'none';
                return;
            }

            fetch('/api/similar-questions', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ title: title, body: body })
            })
                .then(res => res.json())
                .then(data => {
                    if (data.similar_questions && data.similar_questions.length > 0) {
                        renderSimilarQuestions(data.similar_questions);
                    } else {
                        similarContainer.style.display = 'none';
                    }
                })
                .catch(err => console.error('Error fetching similar questions:', err));
        };

        const renderSimilarQuestions = (questions) => {
            similarList.innerHTML = '';
            questions.forEach(q => {
                const item = document.createElement('a');
                item.href = `/question/${q.id}`;
                item.className = 'list-group-item list-group-item-action p-2';
                item.target = '_blank';
                item.innerHTML = `
                    <div class="d-flex w-100 justify-content-between">
                        <h6 class="mb-1 text-truncate" style="max-width: 200px;">${q.title}</h6>
                        <small class="text-muted">${q.similarity}% match</small>
                    </div>
                `;
                similarList.appendChild(item);
            });
            similarContainer.style.display = 'block';
        };

        // Quality Analysis Logic
        const qualityContainer = document.getElementById('quality-analysis-container');
        const qualityScoreValue = document.getElementById('quality-score-value');
        const qualityScoreBar = document.getElementById('quality-score-bar');
        const qualityFeedbackList = document.getElementById('quality-feedback-list');

        const analyzeQuality = () => {
            const title = titleInput.value.trim();
            const body = bodyInput ? bodyInput.value.trim() : '';
            const text = `${title} ${body}`;

            if (text.length < 20) {
                qualityContainer.style.display = 'none';
                return;
            }

            fetch('/api/analyze-quality', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: text })
            })
                .then(res => res.json())
                .then(data => {
                    renderQualityAnalysis(data);
                })
                .catch(err => console.error('Error analyzing quality:', err));
        };

        const renderQualityAnalysis = (data) => {
            qualityScoreValue.textContent = `${data.score}/100`;
            qualityScoreBar.style.width = `${data.score}%`;

            // Color coding
            if (data.score < 40) {
                qualityScoreBar.className = 'progress-bar bg-danger';
                qualityScoreValue.className = 'font-weight-bold text-danger';
            } else if (data.score < 70) {
                qualityScoreBar.className = 'progress-bar bg-warning';
                qualityScoreValue.className = 'font-weight-bold text-warning';
            } else {
                qualityScoreBar.className = 'progress-bar bg-success';
                qualityScoreValue.className = 'font-weight-bold text-success';
            }

            // Feedback
            qualityFeedbackList.innerHTML = '';
            if (data.feedback && data.feedback.length > 0) {
                data.feedback.forEach(msg => {
                    const p = document.createElement('p');
                    p.className = 'small text-muted mb-1';
                    p.innerHTML = `<i class="fas fa-info-circle"></i> ${msg}`;
                    qualityFeedbackList.appendChild(p);
                });
            } else {
                qualityFeedbackList.innerHTML = '<p class="small text-success mb-0"><i class="fas fa-check"></i> Great content!</p>';
            }

            qualityContainer.style.display = 'block';
        };

        titleInput.addEventListener('input', handleInput);
        if (bodyInput) {
            bodyInput.addEventListener('input', handleInput);
        }
    }

    // Auto-generated Summaries logic (View Question Page)
    const summaryButtons = document.querySelectorAll('.generate-summary-btn');
    summaryButtons.forEach(btn => {
        btn.addEventListener('click', function () {
            const answerId = this.dataset.answerId;
            const text = this.dataset.text;
            const summaryContainer = document.getElementById(`summary-container-${answerId}`);
            const summaryText = document.getElementById(`summary-text-${answerId}`);

            // Toggle visibility
            if (summaryContainer.style.display === 'block') {
                summaryContainer.style.display = 'none';
                this.innerHTML = '<i class="fas fa-magic"></i> Show TL;DR (AI Summary)';
                return;
            }

            // If already generated, just show
            if (summaryText.textContent) {
                summaryContainer.style.display = 'block';
                this.innerHTML = '<i class="fas fa-magic"></i> Hide TL;DR';
                return;
            }

            // Show loading
            this.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Generating...';

            fetch('/api/generate-summary', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: text, max_sentences: 2 })
            })
                .then(res => res.json())
                .then(data => {
                    if (data.summary) {
                        summaryText.textContent = data.summary;
                        summaryContainer.style.display = 'block';
                        this.innerHTML = '<i class="fas fa-magic"></i> Hide TL;DR';
                    } else {
                        this.innerHTML = '<i class="fas fa-exclamation-triangle"></i> Failed to generate';
                    }
                })
                .catch(err => {
                    console.error('Error generating summary:', err);
                    this.innerHTML = '<i class="fas fa-exclamation-triangle"></i> Error';
                });
        });
    });
});
