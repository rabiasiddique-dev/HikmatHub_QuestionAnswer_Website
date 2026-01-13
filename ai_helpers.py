
import math
import re
from collections import Counter
import os

# NLTK imports - keeping these for good tokenization
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize

# Configure NLTK to use /tmp directory for Vercel
nltk_data_path = os.path.join('/tmp', 'nltk_data')
if not os.path.exists(nltk_data_path):
    os.makedirs(nltk_data_path, exist_ok=True)

nltk.data.path.append(nltk_data_path)

try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt', download_dir=nltk_data_path)
    
try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords', download_dir=nltk_data_path)


def preprocess_text(text):
    """Clean and preprocess text for NLP"""
    text = text.lower()
    text = re.sub(r'[^a-zA-Z\s]', '', text)
    tokens = word_tokenize(text)
    stop_words = set(stopwords.words('english'))
    tokens = [word for word in tokens if word not in stop_words and len(word) > 2]
    return tokens # Return list of tokens

# --- Simple TF-IDF Implementation (Pure Python) ---

def compute_tf(tokens):
    """Compute Term Frequency"""
    tf_dict = Counter(tokens)
    total_tokens = len(tokens)
    for word in tf_dict:
        tf_dict[word] = tf_dict[word] / float(total_tokens)
    return tf_dict

def compute_idf(corpus_tokens_list):
    """Compute Inverse Document Frequency"""
    idf_dict = {}
    N = len(corpus_tokens_list)
    
    all_words = set([word for tokens in corpus_tokens_list for word in tokens])
    
    for word in all_words:
        count = sum(1 for tokens in corpus_tokens_list if word in tokens)
        idf_dict[word] = math.log(N / float(count))
    return idf_dict

def compute_tfidf_vector(tokens, idf_dict, all_vocab):
    """Compute TF-IDF vector for a document"""
    tf = compute_tf(tokens)
    vector = []
    for word in all_vocab:
        vector.append(tf.get(word, 0) * idf_dict.get(word, 0))
    return vector

def cosine_similarity_manual(vec1, vec2):
    """Compute Cosine Similarity between two vectors"""
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    magnitude1 = math.sqrt(sum(a * a for a in vec1))
    magnitude2 = math.sqrt(sum(b * b for b in vec2))
    
    if magnitude1 == 0 or magnitude2 == 0:
        return 0.0
    return dot_product / (magnitude1 * magnitude2)

# --- Feature Functions ---

def suggest_tags_tfidf(question_title, question_body, all_tags, top_n=5):
    """Suggest tags using simple frequency match (lighter than full TF-IDF for tags)"""
    question_text = f"{question_title} {question_title} {question_body}".lower()
    
    # Simple keyword extraction based on frequency
    tokens = preprocess_text(question_text)
    word_freq = Counter(tokens)
    keywords = [word for word, count in word_freq.most_common(20)]
    
    suggested_tags = []
    
    # 1. Exact/Partial Match
    for tag in all_tags:
        tag_lower = tag.lower()
        if tag_lower in keywords: # Exact match with keyword
            if tag not in suggested_tags: suggested_tags.append(tag)
            
        for keyword in keywords:
            if keyword in tag_lower or tag_lower in keyword:
                if tag not in suggested_tags: suggested_tags.append(tag)
                break
        if len(suggested_tags) >= top_n: break
    
    return suggested_tags[:top_n]


def find_similar_questions(question_text, existing_questions, threshold=0.3, top_n=5):
    """Find similar questions using Manual TF-IDF"""
    if not existing_questions:
        return []
    
    # Preprocess current question
    new_tokens = preprocess_text(question_text)
    
    # Preprocess all existing questions
    existing_processed = []
    for q in existing_questions:
        txt = f"{q['title']} {q.get('body', '')}"
        existing_processed.append({
            'doc': q,
            'tokens': preprocess_text(txt)
        })
    
    # Build Corpus
    corpus_tokens = [new_tokens] + [item['tokens'] for item in existing_processed]
    
    # Create Vocabulary and IDF
    all_vocab = list(set([w for tokens in corpus_tokens for w in tokens]))
    idf_dict = compute_idf(corpus_tokens)
    
    # Vectorize
    new_vector = compute_tfidf_vector(new_tokens, idf_dict, all_vocab)
    
    results = []
    for item in existing_processed:
        item_vector = compute_tfidf_vector(item['tokens'], idf_dict, all_vocab)
        sim_score = cosine_similarity_manual(new_vector, item_vector)
        
        if sim_score >= threshold:
            results.append({
                'question': item['doc'],
                'similarity': float(sim_score)
            })
            
    # Sort and return
    results.sort(key=lambda x: x['similarity'], reverse=True)
    return results[:top_n]


def analyze_content_quality(text):
    """Analyze content quality (No changes needed, pure python)"""
    score = 0
    feedback = []
    
    text_len = len(text)
    if 50 <= text_len <= 5000: score += 20
    elif text_len < 50: feedback.append("Content is too short.")
    else: feedback.append("Content is too long.")
    
    if '?' in text: score += 10
    if '```' in text or '`' in text: score += 15; feedback.append("Good code formatting!")
    
    paragraphs = text.count('\n\n')
    if paragraphs >= 1: score += 10
    else: feedback.append("Break content into paragraphs.")
    
    words = len(text.split())
    if words >= 20: score += 20
    
    sentences = text.count('.') + text.count('!') + text.count('?')
    if sentences >= 3: score += 15
    
    if text and text[0].isupper(): score += 5
    
    caps_ratio = sum(1 for c in text if c.isupper()) / max(len(text), 1)
    if caps_ratio > 0.3: score -= 5; feedback.append("Too much capitalization.") # Fix logic
    else: score += 5
    
    level = "Excellent" if score >= 70 else "Good" if score >= 40 else "Needs Improvement"
    
    if not feedback: feedback.append("Great content!")
    
    return {'score': min(score, 100), 'level': level, 'feedback': feedback}


def generate_summary(text, max_sentences=3):
    """Generate summary (Pure Python)"""
    sentences = re.split(r'[.!?]+', text)
    sentences = [s.strip() for s in sentences if s.strip()]
    
    if len(sentences) <= max_sentences:
        return text
    
    return '. '.join(sentences[:max_sentences]) + '.'
