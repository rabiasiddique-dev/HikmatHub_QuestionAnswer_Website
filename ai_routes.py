# AI API Routes to add to app.py

# Import AI helpers at top of app.py
# from ai_helpers import suggest_tags_tfidf, find_similar_questions, analyze_content_quality, generate_summary

@app.route('/api/suggest-tags', methods=['POST'])
def api_suggest_tags():
    """API endpoint for smart tag suggestions"""
    try:
        data = request.get_json()
        title = data.get('title', '')
        body = data.get('body', '')
        
        if not title and not body:
            return jsonify({'error': 'Title or body required'}), 400
        
        # Get all existing tags from database
        all_tags_cursor = mongo.db.questions.aggregate([
            {'$unwind': '$tags'},
            {'$group': {'_id': '$tags', 'count': {'$sum': 1}}},
            {'$sort': {'count': -1}},
            {'$limit': 100}
        ])
        
        all_tags = [tag['_id'] for tag in all_tags_cursor]
        
        # Get suggestions
        from ai_helpers import suggest_tags_tfidf
        suggested_tags = suggest_tags_tfidf(title, body, all_tags, top_n=8)
        
        return jsonify({'suggested_tags': suggested_tags})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/similar-questions', methods=['POST'])
def api_similar_questions():
    """API endpoint to find similar questions"""
    try:
        data = request.get_json()
        title = data.get('title', '')
        body = data.get('body', '')
        
        if not title:
            return jsonify({'similar_questions': []})
        
        # Combine title and body
        question_text = f"{title} {body}"
        
        # Get recent questions (last 500)
        existing_questions = list(mongo.db.questions.find(
            {},
            {'title': 1, 'body': 1, '_id': 1}
        ).sort('timestamp', -1).limit(500))
        
        # Find similar questions
        from ai_helpers import find_similar_questions
        similar = find_similar_questions(question_text, existing_questions, threshold=0.5, top_n=5)
        
        # Format results
        results = []
        for item in similar:
            q = item['question']
            results.append({
                'id': str(q['_id']),
                'title': q['title'],
                'similarity': round(item['similarity'] * 100, 1)
            })
        
        return jsonify({'similar_questions': results})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/analyze-quality', methods=['POST'])
def api_analyze_quality():
    """API endpoint for content quality analysis"""
    try:
        data = request.get_json()
        text = data.get('text', '')
        
        if not text:
            return jsonify({'error': 'Text required'}), 400
        
        # Analyze quality
        from ai_helpers import analyze_content_quality
        analysis = analyze_content_quality(text)
        
        return jsonify(analysis)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/generate-summary', methods=['POST'])
def api_generate_summary():
    """API endpoint for summary generation"""
    try:
        data = request.get_json()
        text = data.get('text', '')
        max_sentences = data.get('max_sentences', 3)
        
        if not text:
            return jsonify({'error': 'Text required'}), 400
        
        # Generate summary
        from ai_helpers import generate_summary
        summary = generate_summary(text, max_sentences)
        
        return jsonify({'summary': summary})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
