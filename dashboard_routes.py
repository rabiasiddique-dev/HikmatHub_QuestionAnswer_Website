# Dashboard and Bookmark Routes to add to app.py

@app.route('/dashboard')
@login_required
def dashboard():
    """User dashboard with activity, bookmarks, and stats"""
    user_id = ObjectId(current_user.id)
    
    # Get user's bookmarks
    user_doc = mongo.db.users.find_one({'_id': user_id})
    bookmarks = user_doc.get('bookmarks', [])
    following_tags = user_doc.get('following_tags', [])
    following_user_ids = user_doc.get('following_users', [])
    
    # Get bookmarked questions
    bookmarked_questions = []
    if bookmarks:
        for q_doc in mongo.db.questions.find({'_id': {'$in': bookmarks}}):
            author = mongo.db.users.find_one({'_id': q_doc['author_id']})
            q_doc.update({
                'author_username': author['username'] if author else 'Unknown',
                'answers_count': mongo.db.answers.count_documents({'question_id': q_doc['_id']}),
                'net_votes': len(q_doc.get('upvotes', [])) - len(q_doc.get('downvotes', []))
            })
            bookmarked_questions.append(q_doc)
    
    # Get following users
    following_users = list(mongo.db.users.find(
        {'_id': {'$in': following_user_ids}},
        {'username': 1, 'reputation': 1}
    ))
    
    # Get recent activity
    activities = []
    
    # Questions asked
    recent_questions = mongo.db.questions.find(
        {'author_id': user_id}
    ).sort('timestamp', -1).limit(5)
    
    for q in recent_questions:
        activities.append({
            'icon': 'question-circle',
            'text': f'Asked: <a href="/question/{q["_id"]}">{q["title"]}</a>',
            'timestamp': q['timestamp']
        })
    
    # Answers posted
    recent_answers = mongo.db.answers.find(
        {'author_id': user_id}
    ).sort('timestamp', -1).limit(5)
    
    for a in recent_answers:
        question = mongo.db.questions.find_one({'_id': a['question_id']})
        if question:
            activities.append({
                'icon': 'reply',
                'text': f'Answered: <a href="/question/{question["_id"]}">{question["title"]}</a>',
                'timestamp': a['timestamp']
            })
    
    # Sort activities by timestamp
    activities.sort(key=lambda x: x['timestamp'], reverse=True)
    activities = activities[:10]
    
    # Calculate stats
    stats = {
        'questions_asked': mongo.db.questions.count_documents({'author_id': user_id}),
        'answers_posted': mongo.db.answers.count_documents({'author_id': user_id}),
        'accepted_answers': mongo.db.answers.count_documents({
            'author_id': user_id,
            '_id': {'$in': [q.get('best_answer_id') for q in mongo.db.questions.find({}, {'best_answer_id': 1}) if q.get('best_answer_id')]}
        })
    }
    
    return render_template('dashboard.html',
                         activities=activities,
                         bookmarked_questions=bookmarked_questions,
                         following_tags=following_tags,
                         following_users=following_users,
                         stats=stats)


@app.route('/api/bookmark/<question_id>', methods=['POST'])
@login_required
def toggle_bookmark(question_id):
    """Toggle bookmark for a question"""
    try:
        user_id = ObjectId(current_user.id)
        q_id = ObjectId(question_id)
        
        user_doc = mongo.db.users.find_one({'_id': user_id})
        bookmarks = user_doc.get('bookmarks', [])
        
        if q_id in bookmarks:
            # Remove bookmark
            mongo.db.users.update_one(
                {'_id': user_id},
                {'$pull': {'bookmarks': q_id}}
            )
            return jsonify({'bookmarked': False, 'message': 'Bookmark removed'})
        else:
            # Add bookmark
            mongo.db.users.update_one(
                {'_id': user_id},
                {'$addToSet': {'bookmarks': q_id}}
            )
            return jsonify({'bookmarked': True, 'message': 'Question bookmarked'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/upload/image', methods=['POST'])
@login_required
def upload_image():
    """Upload image to Cloudinary (placeholder - requires cloudinary package)"""
    try:
        if 'image' not in request.files:
            return jsonify({'error': 'No image provided'}), 400
        
        file = request.files['image']
        
        # For now, return a placeholder
        # TODO: Install cloudinary and configure
        # import cloudinary
        # import cloudinary.uploader
        # result = cloudinary.uploader.upload(file)
        # return jsonify({'url': result['secure_url']})
        
        return jsonify({
            'success': False,
            'message': 'Image upload requires Cloudinary configuration. Please add CLOUDINARY credentials to .env'
        }), 501
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
