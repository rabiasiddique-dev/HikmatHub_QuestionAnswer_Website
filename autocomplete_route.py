# Add this after the search_results route in app.py

@app.route('/api/autocomplete')
def autocomplete():
    """API endpoint for search autocomplete suggestions"""
    query = request.args.get('q', '').strip()
    
    if len(query) < 2:
        return jsonify({'questions': [], 'tags': []})
    
    try:
        # Search in question titles
        regex = re.compile(query, re.IGNORECASE)
        questions = mongo.db.questions.find(
            {'title': {'$regex': regex}},
            {'title': 1, '_id': 1}
        ).limit(5)
        
        question_results = [{'id': str(q['_id']), 'title': q['title']} for q in questions]
        
        # Get matching tags
        tags = mongo.db.questions.aggregate([
            {'$unwind': '$tags'},
            {'$match': {'tags': {'$regex': regex}}},
            {'$group': {'_id': '$tags', 'count': {'$sum': 1}}},
            {'$sort': {'count': -1}},
            {'$limit': 5}
        ])
        
        tag_results = [{'tag': t['_id'], 'count': t['count']} for t in tags]
        
        return jsonify({
            'questions': question_results,
            'tags': tag_results
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
