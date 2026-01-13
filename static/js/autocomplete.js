// Autocomplete functionality
let autocompleteTimeout;
const searchInput = document.querySelector('.nav-search-form input[type="search"]');
const autocompleteContainer = document.createElement('div');
autocompleteContainer.className = 'autocomplete-dropdown';
autocompleteContainer.style.display = 'none';

if (searchInput) {
    searchInput.parentElement.style.position = 'relative';
    searchInput.parentElement.appendChild(autocompleteContainer);

    searchInput.addEventListener('input', function (e) {
        const query = e.target.value.trim();

        // Clear previous timeout
        clearTimeout(autocompleteTimeout);

        if (query.length < 2) {
            autocompleteContainer.style.display = 'none';
            return;
        }

        // Debounce API call
        autocompleteTimeout = setTimeout(() => {
            fetch(`/api/autocomplete?q=${encodeURIComponent(query)}`)
                .then(res => res.json())
                .then(data => {
                    displayAutocomplete(data);
                })
                .catch(err => console.error('Autocomplete error:', err));
        }, 300);
    });

    // Close autocomplete when clicking outside
    document.addEventListener('click', function (e) {
        if (!searchInput.contains(e.target) && !autocompleteContainer.contains(e.target)) {
            autocompleteContainer.style.display = 'none';
        }
    });
}

function displayAutocomplete(data) {
    if (!data.questions.length && !data.tags.length) {
        autocompleteContainer.style.display = 'none';
        return;
    }

    let html = '';

    if (data.questions.length) {
        html += '<div class="autocomplete-section"><div class="autocomplete-header">Questions</div>';
        data.questions.forEach(q => {
            html += `<a href="/question/${q.id}" class="autocomplete-item">
                <i class="fas fa-question-circle"></i> ${q.title}
            </a>`;
        });
        html += '</div>';
    }

    if (data.tags.length) {
        html += '<div class="autocomplete-section"><div class="autocomplete-header">Tags</div>';
        data.tags.forEach(t => {
            html += `<a href="/search?tag=${encodeURIComponent(t.tag)}" class="autocomplete-item">
                <i class="fas fa-tag"></i> ${t.tag} <span class="tag-count">(${t.count})</span>
            </a>`;
        });
        html += '</div>';
    }

    autocompleteContainer.innerHTML = html;
    autocompleteContainer.style.display = 'block';
}
