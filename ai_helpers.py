# AI Helper Functions for HikmatHub
# Smart Tag Suggestions using TF-IDF

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import re
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize

# Download required NLTK data (run once)
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')
    
try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords')


def preprocess_text(text):
    """Clean and preprocess text for NLP"""
    # Convert to lowercase
    text = text.lower()
    
    # Remove special characters and numbers
    text = re.sub(r'[^a-zA-Z\s]', '', text)
    
    # Tokenize
    tokens = word_tokenize(text)
    
    # Remove stopwords
    stop_words = set(stopwords.words('english'))
    tokens = [word for word in tokens if word not in stop_words and len(word) > 2]
    
    return ' '.join(tokens)


def suggest_tags_tfidf(question_title, question_body, all_tags, top_n=5):
    """
    Suggest tags for a question using TF-IDF
    
    Args:
        question_title: Question title
        question_body: Question body
        all_tags: List of all existing tags in database
        top_n: Number of tags to suggest
    
    Returns:
        List of suggested tags
    """
    # Combine title and body (title weighted more)
    question_text = f"{question_title} {question_title} {question_body}"
    
    # Preprocess
    processed_question = preprocess_text(question_text)
    
    # Extract keywords from question
    words = processed_question.split()
    word_freq = {}
    for word in words:
        word_freq[word] = word_freq.get(word, 0) + 1
    
    # Sort by frequency
    sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
    
    # Get top keywords
    keywords = [word for word, freq in sorted_words[:20]]
    
    # Match with existing tags
    suggested_tags = []
    for tag in all_tags:
        tag_lower = tag.lower()
        # Check if tag matches any keyword
        for keyword in keywords:
            if keyword in tag_lower or tag_lower in keyword:
                if tag not in suggested_tags:
                    suggested_tags.append(tag)
                    break
        
        if len(suggested_tags) >= top_n:
            break
    
    # If not enough tags found, add most common tags
    if len(suggested_tags) < top_n:
        # Add popular tags that match loosely
        for tag in all_tags[:20]:  # Top 20 popular tags
            if tag not in suggested_tags:
                tag_words = tag.lower().split('-')
                for keyword in keywords[:10]:
                    if any(keyword in tw or tw in keyword for tw in tag_words):
                        suggested_tags.append(tag)
                        break
            
            if len(suggested_tags) >= top_n:
                break
    
    return suggested_tags[:top_n]


def find_similar_questions(question_text, existing_questions, threshold=0.6, top_n=5):
    """
    Find similar questions using TF-IDF and cosine similarity
    
    Args:
        question_text: New question text
        existing_questions: List of dicts with 'title' and 'body'
        threshold: Similarity threshold (0-1)
        top_n: Number of similar questions to return
    
    Returns:
        List of similar questions with similarity scores
    """
    if not existing_questions:
        return []
    
    # Prepare texts
    new_text = preprocess_text(question_text)
    existing_texts = [preprocess_text(f"{q['title']} {q.get('body', '')}") for q in existing_questions]
    
    # Create TF-IDF vectors
    vectorizer = TfidfVectorizer(max_features=100)
    
    try:
        # Fit on all texts
        all_texts = [new_text] + existing_texts
        tfidf_matrix = vectorizer.fit_transform(all_texts)
        
        # Calculate similarity
        similarities = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:]).flatten()
        
        # Get indices of similar questions
        similar_indices = []
        for idx, score in enumerate(similarities):
            if score >= threshold:
                similar_indices.append((idx, score))
        
        # Sort by similarity score
        similar_indices.sort(key=lambda x: x[1], reverse=True)
        
        # Return top N
        results = []
        for idx, score in similar_indices[:top_n]:
            results.append({
                'question': existing_questions[idx],
                'similarity': float(score)
            })
        
        return results
    except:
        return []


def analyze_content_quality(text):
    """
    Analyze content quality and provide score
    
    Returns:
        dict with 'score' (0-100) and 'feedback' (list of suggestions)
    """
    score = 0
    feedback = []
    
    # Length check (50-5000 chars)
    text_len = len(text)
    if 50 <= text_len <= 5000:
        score += 20
    elif text_len < 50:
        feedback.append("Content is too short. Add more details.")
    else:
        feedback.append("Content is very long. Consider being more concise.")
    
    # Question mark check (for questions)
    if '?' in text:
        score += 10
    
    # Code block check
    if '```' in text or '`' in text:
        score += 15
        feedback.append("Good use of code formatting!")
    
    # Paragraph check
    paragraphs = text.count('\n\n')
    if paragraphs >= 1:
        score += 10
    else:
        feedback.append("Consider breaking content into paragraphs.")
    
    # Word count
    words = len(text.split())
    if words >= 20:
        score += 20
    elif words < 10:
        feedback.append("Add more words to explain better.")
    
    # Sentence count
    sentences = text.count('.') + text.count('!') + text.count('?')
    if sentences >= 3:
        score += 15
    
    # Capitalization check
    if text[0].isupper():
        score += 5
    
    # No excessive caps
    caps_ratio = sum(1 for c in text if c.isupper()) / max(len(text), 1)
    if caps_ratio < 0.3:
        score += 5
    else:
        feedback.append("Avoid excessive capitalization.")
    
    # Quality level
    if score >= 70:
        level = "Excellent"
    elif score >= 40:
        level = "Good"
    else:
        level = "Needs Improvement"
    
    return {
        'score': min(score, 100),
        'level': level,
        'feedback': feedback
    }


def generate_summary(text, max_sentences=3):
    """
    Generate a simple summary (TL;DR)
    
    Args:
        text: Full text to summarize
        max_sentences: Maximum sentences in summary
    
    Returns:
        Summary string
    """
    # Split into sentences
    sentences = re.split(r'[.!?]+', text)
    sentences = [s.strip() for s in sentences if s.strip()]
    
    # If short enough, return as is
    if len(sentences) <= max_sentences:
        return text
    
    # Simple approach: Return first N sentences
    summary = '. '.join(sentences[:max_sentences]) + '.'
    
    return summary
