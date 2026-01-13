document.addEventListener('DOMContentLoaded', function () {

    // --- Navbar Toggler for Mobile ---
    const navToggler = document.querySelector('.nav-toggler');
    const navMenu = document.querySelector('.nav-menu');
    if (navToggler && navMenu) {
        navToggler.addEventListener('click', () => {
            navMenu.classList.toggle('active');
            navToggler.classList.toggle('open'); // For burger animation if CSS is set up
        });
    }

    // --- Dark Mode Theme Toggle Logic ---
    const themeToggleBtn = document.getElementById('theme-toggle');
    const currentTheme = localStorage.getItem('theme');

    // Apply saved theme on load (FOUC is partially handled in base.html too if added)
    if (currentTheme) {
        document.documentElement.setAttribute('data-theme', currentTheme);
    }

    if (themeToggleBtn) {
        themeToggleBtn.addEventListener('click', function () {
            let theme = document.documentElement.getAttribute('data-theme');
            if (theme === 'dark') {
                theme = 'light';
                document.documentElement.removeAttribute('data-theme');
            } else {
                theme = 'dark';
                document.documentElement.setAttribute('data-theme', 'dark');
            }
            localStorage.setItem('theme', theme);
        });
    }

    // --- Smooth Scroll for Internal Links (if any) ---
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const targetElement = document.querySelector(this.getAttribute('href'));
            if (targetElement) {
                targetElement.scrollIntoView({ behavior: 'smooth' });
            }
        });
    });

    // --- Alert Auto-Dismiss & Helper Functions ---
    function dismissAlert(alertElement) {
        if (alertElement && alertElement.parentElement) {
            alertElement.style.transition = 'opacity 0.5s ease, transform 0.5s ease';
            alertElement.style.opacity = '0';
            alertElement.style.transform = 'translateY(-20px)';
            setTimeout(() => {
                if (alertElement.parentNode) {
                    alertElement.remove();
                }
            }, 500);
        }
    }

    document.querySelectorAll('.alert').forEach(alert => {
        const closeButton = document.createElement('button');
        closeButton.setAttribute('type', 'button');
        closeButton.setAttribute('class', 'alert-close-btn');
        closeButton.innerHTML = '×'; // HTML entity for multiplication sign
        closeButton.setAttribute('aria-label', 'Close');
        alert.appendChild(closeButton);
        closeButton.addEventListener('click', function () {
            dismissAlert(this.parentElement);
        });
        setTimeout(() => { dismissAlert(alert); }, 7000); // Auto-dismiss after 7 seconds
    });

    function showFlashMessage(message, category, containerSelector = 'main.container .page-header, main.container:first-child') {
        let flashContainer = document.querySelector(containerSelector);
        if (!flashContainer) {
            flashContainer = document.querySelector('main.container') || document.body;
        }
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${category} alert-dismissible fade show`;
        alertDiv.setAttribute('role', 'alert');
        alertDiv.innerHTML = message; // Use innerHTML to render HTML if message contains it (e.g., error lists)

        const closeBtn = document.createElement('button');
        closeBtn.type = 'button'; closeBtn.className = 'alert-close-btn';
        closeBtn.innerHTML = '×'; closeBtn.setAttribute('aria-label', 'Close');
        closeBtn.onclick = function () { dismissAlert(alertDiv); };
        alertDiv.appendChild(closeBtn);

        if (flashContainer.firstChild) {
            flashContainer.insertBefore(alertDiv, flashContainer.firstChild);
        } else {
            flashContainer.appendChild(alertDiv);
        }
        setTimeout(() => { dismissAlert(alertDiv); }, 7000);
    }

    // --- Voting Logic (Questions, Answers, Comments) using Event Delegation ---
    document.body.addEventListener('click', async function (e) {
        const button = e.target.closest('.vote-btn.upvote-item, .vote-btn.downvote-item');
        if (!button || button.disabled) return;

        const itemId = button.dataset.itemId;
        const voteType = button.dataset.voteType;
        const itemType = button.dataset.itemType; // 'question', 'answer', or 'comment'
        const parentVotingSection = button.closest('.voting-section');

        parentVotingSection.querySelectorAll('.vote-btn').forEach(btn => btn.disabled = true);

        try {
            const response = await fetch(`/vote/${itemType}/${itemId}/${voteType}`, {
                method: 'POST',
                headers: { 'X-Requested-With': 'XMLHttpRequest' /*, 'X-CSRFToken': getCsrfToken() */ }
            });
            const data = await response.json();

            if (response.ok && data.status === 'success') {
                const prefix = itemType.charAt(0); // 'q', 'a', or 'c'
                const upvoteSpan = parentVotingSection.querySelector(`#${prefix}-upvotes-${itemId}`);
                const downvoteSpan = parentVotingSection.querySelector(`#${prefix}-downvotes-${itemId}`);
                // const netVoteSpan = parentVotingSection.querySelector(`#${prefix}-net-votes-${itemId}`); // If displaying net votes

                if (upvoteSpan) upvoteSpan.textContent = data.upvotes;
                if (downvoteSpan) downvoteSpan.textContent = data.downvotes;
                // if (netVoteSpan) netVoteSpan.textContent = data.net_votes;

                // Update active classes based on returned vote state (more robust if server returns user's current vote)
                // For now, just visually activate the clicked button and deactivate others in this section
                parentVotingSection.querySelectorAll('.vote-btn').forEach(btn => btn.classList.remove('active'));
                // This simplified active state might not reflect the true toggle state accurately without server feedback on current vote.
                // button.classList.add('active'); 
            } else {
                showFlashMessage(data.message || `Voting failed for ${itemType}.`, 'danger');
            }
        } catch (error) {
            console.error('Vote fetch error:', error);
            showFlashMessage('Could not connect to server to vote.', 'danger');
        } finally {
            parentVotingSection.querySelectorAll('.vote-btn').forEach(btn => btn.disabled = false);
        }
    });

    // --- Footer Contact Form Submission ---
    const footerContactForm = document.getElementById('footer-contact-form');
    if (footerContactForm) {
        const footerFormStatus = document.getElementById('footer-form-status');
        footerContactForm.addEventListener('submit', async function (e) {
            e.preventDefault();
            const submitButton = this.querySelector('button[type="submit"]');
            const originalButtonText = submitButton.textContent;
            submitButton.disabled = true; submitButton.textContent = 'Sending...';
            const formData = new FormData(footerContactForm);

            if (footerFormStatus) {
                footerFormStatus.style.display = 'none';
                footerFormStatus.className = 'form-status-message';
            }
            try {
                const response = await fetch(footerContactForm.action, { method: 'POST', body: formData, headers: { 'X-Requested-With': 'XMLHttpRequest' } });
                const result = await response.json();
                if (footerFormStatus) {
                    if (response.ok && result.status === 'success') {
                        footerFormStatus.textContent = result.message; footerFormStatus.classList.add('success');
                        footerContactForm.reset();
                    } else {
                        let errorMessage = result.message || 'An error occurred.';
                        if (result.errors) {
                            errorMessage = "Please correct the following errors:<ul>";
                            for (const field in result.errors) {
                                errorMessage += `<li>${result.errors[field]}</li>`;
                            }
                            errorMessage += "</ul>";
                            footerFormStatus.innerHTML = errorMessage;
                        } else { footerFormStatus.textContent = errorMessage; }
                        footerFormStatus.classList.add('error');
                    }
                }
            } catch (error) {
                console.error('Footer form submission error:', error);
                if (footerFormStatus) { footerFormStatus.textContent = 'Could not connect. Please try again.'; footerFormStatus.classList.add('error'); }
            } finally {
                if (footerFormStatus) footerFormStatus.style.display = 'block';
                submitButton.disabled = false; submitButton.textContent = originalButtonText;
            }
        });
    }

    // --- Comment Functionality (Add, Edit, Delete) using Event Delegation ---

    // Helper to update comment count display
    function updateCommentCountDisplay(commentsSectionElement, change) {
        const countHeader = commentsSectionElement.querySelector('h5, h6');
        if (countHeader) {
            const countMatch = countHeader.textContent.match(/\((\d+)\)/); // Extracts number from (X)
            let currentCount = countMatch ? parseInt(countMatch[1]) : 0;
            currentCount += change;
            currentCount = Math.max(0, currentCount); // Ensure count doesn't go below zero
            countHeader.textContent = countHeader.textContent.replace(/\(\d+\)/, `(${currentCount})`);

            const commentsList = commentsSectionElement.querySelector('.comments-list');
            const noCommentsMessage = commentsList.querySelector('p.small.text-muted.no-comments-yet');
            if (currentCount === 0 && !noCommentsMessage) {
                const p = document.createElement('p');
                p.className = 'small text-muted no-comments-yet';
                p.textContent = commentsSectionElement.id.includes('question') ? 'No comments yet on this question.' : 'No comments yet on this answer.';
                commentsList.appendChild(p);
            } else if (currentCount > 0 && noCommentsMessage) {
                noCommentsMessage.remove();
            }
        }
    }

    // Delegated event listener for submitting NEW comments
    document.body.addEventListener('submit', async function (e) {
        if (e.target.matches('form.comment-form')) { // New comment forms
            e.preventDefault();
            const form = e.target;
            const commentInput = form.querySelector('.comment-input');
            const commentBody = commentInput.value.trim();
            const submitButton = form.querySelector('.submit-comment-btn');
            const originalButtonText = submitButton.textContent;
            const formActionUrl = form.action;

            if (commentBody.length < 3 || commentBody.length > 500) {
                showFlashMessage('Comment must be between 3 and 500 characters.', 'warning');
                return;
            }
            submitButton.disabled = true; submitButton.textContent = 'Posting...';
            try {
                const formData = new FormData(); formData.append('body', commentBody);
                const response = await fetch(formActionUrl, { method: 'POST', body: formData, headers: { 'X-Requested-With': 'XMLHttpRequest' } });
                const result = await response.json();
                if (response.ok && result.status === 'success') {
                    const commentsSectionElement = document.getElementById(`comments-${result.parent_type}-${result.parent_id_str}`);
                    const commentsListContainer = commentsSectionElement.querySelector('.comments-list');
                    if (commentsListContainer) {
                        const tempDiv = document.createElement('div'); tempDiv.innerHTML = result.comment_html.trim();
                        const newCommentElement = tempDiv.firstChild;
                        commentsListContainer.appendChild(newCommentElement);
                        updateCommentCountDisplay(commentsSectionElement, 1);
                    }
                    commentInput.value = '';
                } else {
                    showFlashMessage(result.message || 'Could not post comment.', 'danger');
                }
            } catch (error) {
                console.error('Comment submission error:', error);
                showFlashMessage('An error occurred while posting your comment.', 'danger');
            } finally {
                submitButton.disabled = false; submitButton.textContent = originalButtonText;
            }
        }
    });

    // Delegated event listener for actions WITHIN a comment (Edit trigger, Cancel Edit, Delete trigger)
    // And for submitting the EDIT form
    document.body.addEventListener('click', async function (e) {
        const editTrigger = e.target.closest('.edit-comment-trigger');
        const cancelEditBtn = e.target.closest('.cancel-edit-comment-btn');
        const deleteTrigger = e.target.closest('.delete-comment-trigger');

        if (editTrigger) {
            e.preventDefault();
            const commentId = editTrigger.dataset.commentId;
            const commentDiv = document.getElementById(`comment-${commentId}`);
            if (!commentDiv) return;
            const bodyDiv = commentDiv.querySelector('.comment-body');
            const editForm = commentDiv.querySelector('.edit-comment-form');
            if (bodyDiv && editForm) {
                bodyDiv.style.display = 'none';
                editForm.style.display = 'block';
                const inputField = editForm.querySelector('.comment-edit-input');
                if (inputField) { inputField.value = bodyDiv.textContent.trim(); inputField.focus(); }
            }
        } else if (cancelEditBtn) {
            e.preventDefault();
            const commentDiv = cancelEditBtn.closest('.comment');
            if (!commentDiv) return;
            const bodyDiv = commentDiv.querySelector('.comment-body');
            const editForm = commentDiv.querySelector('.edit-comment-form');
            if (bodyDiv && editForm) { bodyDiv.style.display = 'block'; editForm.style.display = 'none'; }
        } else if (deleteTrigger) {
            e.preventDefault();
            if (!confirm('Are you sure you want to delete this comment?')) return;

            const commentId = deleteTrigger.dataset.commentId;
            const originalButtonText = deleteTrigger.innerHTML;
            deleteTrigger.innerHTML = 'Deleting...';
            deleteTrigger.style.pointerEvents = 'none';

            try {
                const response = await fetch(`/comment/delete/${commentId}`, { method: 'POST', headers: { 'X-Requested-With': 'XMLHttpRequest' } });
                const result = await response.json();
                if (response.ok && result.status === 'success') {
                    const commentElement = document.getElementById(`comment-${commentId}`);
                    if (commentElement) {
                        const commentsSectionElement = commentElement.closest('.comments-section');
                        commentElement.remove();
                        if (commentsSectionElement) updateCommentCountDisplay(commentsSectionElement, -1);
                    }
                } else {
                    showFlashMessage(result.message || 'Could not delete comment.', 'danger');
                    deleteTrigger.innerHTML = originalButtonText;
                    deleteTrigger.style.pointerEvents = 'auto';
                }
            } catch (error) {
                showFlashMessage('Error deleting comment.', 'danger');
                deleteTrigger.innerHTML = originalButtonText;
                deleteTrigger.style.pointerEvents = 'auto';
            }
        }
    });

    // Delegated event listener for submitting EDITED comments
    document.body.addEventListener('submit', async function (e) {
        if (e.target.matches('form.edit-comment-form')) { // Edit comment forms
            e.preventDefault();
            const form = e.target;
            const commentId = form.dataset.commentId;
            const newBody = form.querySelector('.comment-edit-input').value.trim();
            const submitButton = form.querySelector('.submit-edit-comment-btn');
            const originalButtonText = submitButton.textContent;

            if (newBody.length < 3 || newBody.length > 500) {
                showFlashMessage("Comment must be between 3 and 500 characters.", "warning");
                return;
            }
            submitButton.disabled = true; submitButton.textContent = 'Saving...';
            try {
                const formData = new FormData(); formData.append('body', newBody);
                const response = await fetch(`/comment/edit/${commentId}`, { method: 'POST', body: formData, headers: { 'X-Requested-With': 'XMLHttpRequest' } });
                const result = await response.json();
                const commentDiv = document.getElementById(`comment-${commentId}`);
                const bodyDiv = commentDiv.querySelector('.comment-body');

                if (response.ok && result.status === 'success') {
                    if (bodyDiv) { bodyDiv.textContent = result.new_body; bodyDiv.style.display = 'block'; }
                    form.style.display = 'none';
                    let editedIndicator = commentDiv.querySelector('.edited-indicator');
                    if (!editedIndicator) {
                        editedIndicator = document.createElement('span');
                        editedIndicator.className = 'edited-indicator small ml-1';
                        const timestampSpan = commentDiv.querySelector('.comment-timestamp');
                        if (timestampSpan) timestampSpan.insertAdjacentElement('afterend', editedIndicator);
                    }
                    editedIndicator.textContent = '(edited)';
                    editedIndicator.title = `Edited on ${new Date().toLocaleString()}`;
                } else {
                    showFlashMessage(result.message || 'Could not update comment.', 'danger');
                }
            } catch (error) {
                showFlashMessage('Error updating comment.', 'danger');
            } finally {
                submitButton.disabled = false; submitButton.textContent = originalButtonText;
            }
        }
    });


    // --- Tabbed Content for Profile Page ---
    const tabLinks = document.querySelectorAll('.profile-content-tabs .tab-link');
    const tabContents = document.querySelectorAll('.profile-content-tabs .tab-content');
    function activateTab(tabName) {
        tabLinks.forEach(link => link.classList.toggle('active', link.dataset.tab === tabName));
        tabContents.forEach(content => content.classList.toggle('active', content.id === tabName));
        if (history.pushState) { history.pushState(null, null, '#' + tabName); }
        else { window.location.hash = '#' + tabName; }
    }
    if (tabLinks.length > 0 && tabContents.length > 0) {
        tabLinks.forEach(link => link.addEventListener('click', function (e) { e.preventDefault(); activateTab(this.dataset.tab); }));
        let currentHash = window.location.hash.substring(1);
        if (currentHash && document.getElementById(currentHash) && document.querySelector(`.tab-link[data-tab="${currentHash}"]`)) {
            activateTab(currentHash);
        } else { activateTab(tabLinks[0].dataset.tab); }
    }

    // --- Mark Best Answer AJAX ---
    document.querySelectorAll('.mark-best-answer-form').forEach(form => {
        form.addEventListener('submit', async function (e) {
            e.preventDefault();
            const submitButton = this.querySelector('.mark-best-btn');
            const originalButtonText = submitButton.innerHTML;
            submitButton.disabled = true; submitButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Marking...';
            try {
                const response = await fetch(this.action, { method: 'POST', headers: { 'X-Requested-With': 'XMLHttpRequest' } });
                const result = await response.json();
                if (response.ok && result.status === 'success') { window.location.reload(); }
                else { showFlashMessage(result.message || 'Could not mark best answer.', 'danger'); submitButton.disabled = false; submitButton.innerHTML = originalButtonText; }
            } catch (error) {
                console.error('Mark best answer error:', error);
                showFlashMessage('An error occurred.', 'danger');
                submitButton.disabled = false; submitButton.innerHTML = originalButtonText;
            }
        });
    });

    // --- Notification Related JS ---
    function updateNavbarNotificationCount(count) {
        const countBadge = document.getElementById('notification-count-badge');
        if (countBadge) {
            count = parseInt(count) || 0; // Ensure count is a number
            if (count > 0) { countBadge.textContent = count; countBadge.style.display = 'inline-block'; }
            else { countBadge.style.display = 'none'; }
        }
    }

    document.body.addEventListener('click', async function (e) {
        const notificationLink = e.target.closest('a.notification-link'); // Make selector more specific
        if (notificationLink) {
            const listItem = notificationLink.closest('.notification-item');
            if (listItem && listItem.classList.contains('notification-unread')) {
                const notificationId = listItem.dataset.notificationId;
                // Don't prevent default for the link, let it navigate
                // Mark as read in background
                fetch(`/notifications/mark_read/${notificationId}`, { method: 'POST', headers: { 'X-Requested-With': 'XMLHttpRequest' } })
                    .then(response => response.json())
                    .then(data => {
                        if (data.status === 'success') {
                            listItem.classList.remove('notification-unread');
                            listItem.classList.add('notification-read');
                            updateNavbarNotificationCount(data.new_unread_count);
                        }
                    }).catch(err => console.error("Error marking notification as read on click", err));
            }
        }
    });

    const markAllReadBtn = document.getElementById('mark-all-read-btn');
    if (markAllReadBtn) {
        markAllReadBtn.addEventListener('click', async function () {
            const originalText = this.textContent;
            this.disabled = true; this.textContent = 'Marking...';
            const markAllReadUrl = this.dataset.markAllUrl || '/notifications/mark_all_read'; // Use data attribute
            try {
                const response = await fetch(markAllReadUrl, { method: 'POST', headers: { 'X-Requested-With': 'XMLHttpRequest' } });
                const result = await response.json();
                if (response.ok && result.status === 'success') {
                    document.querySelectorAll('.notification-item.notification-unread').forEach(item => {
                        item.classList.remove('notification-unread');
                        item.classList.add('notification-read');
                    });
                    updateNavbarNotificationCount(0);
                    this.style.display = 'none';
                    showFlashMessage('All notifications marked as read.', 'success');
                } else {
                    showFlashMessage(result.message || 'Could not mark all as read.', 'danger');
                    this.disabled = false; this.textContent = originalText;
                }
            } catch (error) {
                console.error('Mark all read error:', error);
                showFlashMessage('An error occurred.', 'danger');
                this.disabled = false; this.textContent = originalText;
            }
        });
    }

    // --- EasyMDE Initialization for Questions and Answers ---
    const textareas = document.querySelectorAll('.textarea-body');
    textareas.forEach(textarea => {
        const easyMDE = new EasyMDE({
            element: textarea,
            forceSync: true,
            spellChecker: false,
            autosave: {
                enabled: true,
                uniqueId: textarea.id || "hikmat-hub-editor",
                delay: 1000,
            },
            placeholder: textarea.placeholder || "Write your content here...",
            status: ['lines', 'words', 'cursor'],
            renderingConfig: {
                singleLineBreaks: false,
                codeSyntaxHighlighting: true,
            },
        });
    });

}); // End of main DOMContentLoaded listener