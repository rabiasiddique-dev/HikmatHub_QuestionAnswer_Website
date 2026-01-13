# Standard Library Imports
import re
import secrets
import logging
import os
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

# Third-party Library Imports
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, abort
from flask_pymongo import PyMongo
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt
from bson.objectid import ObjectId
from itsdangerous import URLSafeTimedSerializer
from flask_mail import Mail, Message
from flask_dance.contrib.google import make_google_blueprint, google
from flask_dance.consumer import oauth_authorized, oauth_error
from jinja2 import TemplateNotFound # For static_page route
import markdown
import bleach

# WTForms Imports
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, TextAreaField, SubmitField, BooleanField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError, Optional

# --- 1. Configuration ---
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your_very_secret_random_string_for_production_must_change_this')
app.config['MONGO_URI'] = os.environ.get('MONGO_URI') or os.environ.get('MONGODB_URI') or 'mongodb://localhost:27017/hikmat_hub'

# Flask-Mail Configuration
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'True') == 'True'
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME', 'YOUR_EMAIL@gmail.com')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD', 'YOUR_GMAIL_APP_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = (
    os.environ.get('MAIL_SENDER_NAME', 'Hikmat Hub Support'),
    os.environ.get('MAIL_USERNAME', 'YOUR_EMAIL@gmail.com')
)

# Google OAuth Configuration
app.config['GOOGLE_OAUTH_CLIENT_ID'] = os.environ.get('GOOGLE_OAUTH_CLIENT_ID', "YOUR_GOOGLE_CLIENT_ID_HERE")
app.config['GOOGLE_OAUTH_CLIENT_SECRET'] = os.environ.get('GOOGLE_OAUTH_CLIENT_SECRET', "YOUR_GOOGLE_CLIENT_SECRET_HERE")

# --- 2. Extensions Initialization ---
mongo = PyMongo(app)
bcrypt = Bcrypt(app)
mail = Mail(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'

s = URLSafeTimedSerializer(app.config['SECRET_KEY'])
PASSWORD_RESET_SALT = 'hikmat-hub-password-reset-salt' # Use a unique, strong salt

# --- 3. Blueprints ---
# Google OAuth Blueprint
google_bp = make_google_blueprint(
    scope=["openid", "https://www.googleapis.com/auth/userinfo.email", "https://www.googleapis.com/auth/userinfo.profile"],
    offline=True, reprompt_consent=True,
)
app.register_blueprint(google_bp, url_prefix="/login")

# Admin Panel Blueprint (Placeholder for future implementation)
# from admin import admin_bp # Assuming you have an admin blueprint in an 'admin' package
# app.register_blueprint(admin_bp, url_prefix="/admin")


# --- 4. BADGES CONFIGURATION ---
BADGES_CONFIG = {
    "first_questioner": {"name": "Question Starter", "description": "Asked your first question.", "icon_class": "fas fa-question-circle", "icon_color": "var(--info-color)"},
    "first_answerer": {"name": "First Responder", "description": "Posted your first answer.", "icon_class": "fas fa-reply", "icon_color": "var(--info-color)"},
    "curious_mind_5": {"name": "Curious Mind I", "description": "Asked 5 questions.", "icon_class": "fas fa-search-plus", "icon_color": "var(--secondary-color)"},
    "helpful_hand_10": {"name": "Helpful Hand I", "description": "Received 10 upvotes on your answers.", "icon_class": "fas fa-hands-helping", "icon_color": "var(--success-color)"},
    "scholar_100": {"name": "Apprentice Scholar", "description": "Earned 100 reputation points.", "icon_class": "fas fa-graduation-cap", "icon_color": "var(--primary-color)"},
    "wordsmith_bio": {"name": "Wordsmith", "description": "Completed your profile bio.", "icon_class": "fas fa-user-edit", "icon_color": "#6c757d"}
}

# --- 5. User Model & Flask-Login ---
class User(UserMixin):
    # ... (User class definition as before) ...
    def __init__(self, user_data):
        self.id = str(user_data['_id'])
        self.username = user_data['username']
        self.email = user_data['email']
        self.password_hash = user_data.get('password_hash', None)
        self.reputation = user_data.get('reputation', 0)
        self.joined_date = user_data.get('joined_date', datetime.now(timezone.utc))
        self.bio = user_data.get('bio', '')
        self.role = user_data.get('role', 'user')
        self.is_admin = (self.role == 'admin')
        self.google_id = user_data.get('google_id')

    @staticmethod
    def get(user_id):
        try: user_data = mongo.db.users.find_one({'_id': ObjectId(user_id)}); return User(user_data) if user_data else None
        except Exception as e: app.logger.error(f"Error fetching user {user_id}: {e}"); return None
@login_manager.user_loader
def load_user(user_id): return User.get(user_id)

# --- 6. Forms (Flask-WTF) ---
# ... (All form class definitions: RegistrationForm, LoginForm, QuestionForm, AnswerForm, FooterContactForm, EditProfileForm, CommentForm, RequestPasswordResetForm, ResetPasswordForm - as before) ...
class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=30)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6, max=60)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password', message='Passwords must match')])
    submit = SubmitField('Sign Up')
    def validate_username(self, username):
        if mongo.db.users.find_one({'username': username.data}): raise ValidationError('That username is taken.')
    def validate_email(self, email):
        if mongo.db.users.find_one({'email': email.data}): raise ValidationError('That email is already registered.')

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember = BooleanField('Remember Me')
    submit = SubmitField('Login')

class QuestionForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired(), Length(min=10, max=200)])
    body = TextAreaField('Body (Details)', validators=[DataRequired(), Length(min=20)])
    tags = StringField('Tags (comma-separated)', validators=[DataRequired()])
    submit = SubmitField('Ask Question')

class AnswerForm(FlaskForm):
    body = TextAreaField('Your Answer', validators=[DataRequired(), Length(min=15)])
    submit = SubmitField('Post Answer')

class FooterContactForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    message = TextAreaField('Message', validators=[DataRequired(), Length(min=10, max=500)])
    submit = SubmitField('Send Message')

class EditProfileForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=30)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    bio = TextAreaField('About Me (Bio)', validators=[Optional(), Length(max=500)])
    current_password = PasswordField('Current Password', validators=[Optional(), Length(min=6)])
    new_password = PasswordField('New Password', validators=[Optional(), Length(min=6)])
    confirm_new_password = PasswordField('Confirm New Password', validators=[Optional(), EqualTo('new_password', message='New passwords must match.')])
    submit = SubmitField('Update Profile')
    def __init__(self, original_username, original_email, *args, **kwargs):
        super(EditProfileForm, self).__init__(*args, **kwargs)
        self.original_username, self.original_email = original_username, original_email
    def validate_username(self, username):
        if username.data != self.original_username and mongo.db.users.find_one({'username': username.data}):
            raise ValidationError('That username is taken.')
    def validate_email(self, email):
        if email.data != self.original_email and mongo.db.users.find_one({'email': email.data}):
            raise ValidationError('That email is registered by another user.')
    def validate_new_password(self, new_password):
        if new_password.data and not self.current_password.data:
            raise ValidationError('Current password is required to set a new password.')

class CommentForm(FlaskForm):
    body = TextAreaField('Your Comment', validators=[DataRequired(), Length(min=3, max=500)])
    submit = SubmitField('Post Comment')

class RequestPasswordResetForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    submit = SubmitField('Request Password Reset')

class ResetPasswordForm(FlaskForm):
    password = PasswordField('New Password', validators=[DataRequired(), Length(min=6, max=60)])
    confirm_password = PasswordField('Confirm New Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Reset Password')


# --- 7. Helper Functions ---
# ... (create_notification, send_password_reset_email, award_badge_if_eligible, check_and_award_all_badges, _handle_vote - as before) ...
def create_notification(recipient_id, actor_id, action_type, target_id, reference_id=None, target_parent_id=None):
    if recipient_id == actor_id: return
    notification_doc = {'recipient_id': recipient_id, 'actor_id': actor_id, 'action_type': action_type, 'target_id': target_id, 'is_read': False, 'timestamp': datetime.now(timezone.utc)}
    if reference_id: notification_doc['reference_id'] = reference_id
    if target_parent_id: notification_doc['target_parent_id'] = target_parent_id
    mongo.db.notifications.insert_one(notification_doc)

def send_password_reset_email(user_email, token):
    msg_title = 'Password Reset Request - Hikmat Hub'
    reset_url = url_for('reset_token', token=token, _external=True)
    html_body = render_template('email/password_reset_email.html', reset_url=reset_url)
    msg = Message(subject=msg_title, recipients=[user_email], html=html_body)
    try: mail.send(msg); app.logger.info(f"Password reset email sent to {user_email}"); return True
    except Exception as e: app.logger.error(f"Failed to send password reset email to {user_email}: {e}"); return False

def award_badge_if_eligible(user_id_obj, badge_id):
    if not mongo.db.user_badges.find_one({'user_id': user_id_obj, 'badge_id': badge_id}) and badge_id in BADGES_CONFIG:
        mongo.db.user_badges.insert_one({'user_id': user_id_obj, 'badge_id': badge_id, 'awarded_at': datetime.now(timezone.utc)})
        user_info = mongo.db.users.find_one({'_id': user_id_obj}, {'username': 1})
        username = user_info['username'] if user_info else "User"
        badge_name = BADGES_CONFIG[badge_id]['name']
        flash(f"Congratulations, {username}! You've earned the '{badge_name}' badge!", "success")
        create_notification(recipient_id=user_id_obj, actor_id=user_id_obj, action_type='new_badge', target_id=user_id_obj, reference_id=badge_id)

def check_and_award_all_badges(user_id_obj):
    user_doc = mongo.db.users.find_one({'_id': user_id_obj})
    if not user_doc: return
    if mongo.db.questions.count_documents({'author_id': user_id_obj}) >= 1: award_badge_if_eligible(user_id_obj, "first_questioner")
    if mongo.db.answers.count_documents({'author_id': user_id_obj}) >= 1: award_badge_if_eligible(user_id_obj, "first_answerer")
    if mongo.db.questions.count_documents({'author_id': user_id_obj}) >= 5: award_badge_if_eligible(user_id_obj, "curious_mind_5")
    total_answer_upvotes = sum(len(ans.get('upvotes', [])) for ans in mongo.db.answers.find({'author_id': user_id_obj}, {'upvotes': 1}))
    if total_answer_upvotes >= 10: award_badge_if_eligible(user_id_obj, "helpful_hand_10")
    if user_doc.get('reputation', 0) >= 100: award_badge_if_eligible(user_id_obj, "scholar_100")
    if user_doc.get('bio', '').strip(): award_badge_if_eligible(user_id_obj, "wordsmith_bio")

def get_level_info(reputation):
    levels = [
        {"name": "Apprentice", "min": 0, "max": 100, "icon": "fa-seedling"},
        {"name": "Knowledge Seeker", "min": 100, "max": 500, "icon": "fa-search"},
        {"name": "Wise Sage", "min": 500, "max": 1500, "icon": "fa-book-reader"},
        {"name": "Guardian of Wisdom", "min": 1500, "max": 4000, "icon": "fa-shield-alt"},
        {"name": "Grandmaster", "min": 4000, "max": 999999, "icon": "fa-crown"}
    ]
    for i, level in enumerate(levels):
        if reputation < level["max"]:
            progress = ((reputation - level["min"]) / (level["max"] - level["min"])) * 100
            return {
                "current_level": i + 1,
                "title": level["name"],
                "icon": level["icon"],
                "progress": round(progress, 1),
                "next_level_rep": level["max"],
                "remaining_rep": level["max"] - reputation
            }
    return {
        "current_level": len(levels),
        "title": levels[-1]["name"],
        "icon": levels[-1]["icon"],
        "progress": 100,
        "next_level_rep": None,
        "remaining_rep": 0
    }

def _handle_vote(collection_name, item_id_str, vote_type, points_for_upvote=10, points_for_downvote=-2, points_self_downvote=-1):
    if not current_user.is_authenticated: return jsonify({'status': 'error', 'message': 'You must be logged in to vote.'}), 401
    try: item_id_obj, user_id_obj = ObjectId(item_id_str), ObjectId(current_user.id)
    except Exception: return jsonify({'status': 'error', 'message': 'Invalid ID format.'}), 400
    collection = getattr(mongo.db, collection_name)
    item = collection.find_one({'_id': item_id_obj})
    if not item: return jsonify({'status': 'error', 'message': f'{collection_name[:-1].capitalize()} not found.'}), 404
    if 'author_id' not in item: app.logger.error(f"Item {item_id_str} in {collection_name} missing author_id for voting."); return jsonify({'status': 'error', 'message': 'Cannot process vote.'}), 500
    author_id = item['author_id']
    if author_id == user_id_obj and vote_type == 'upvote' and collection_name != 'comments': return jsonify({'status': 'error', 'message': 'You cannot upvote your own content.'}), 403
    upvoted_by_user, downvoted_by_user = user_id_obj in item.get('upvotes', []), user_id_obj in item.get('downvotes', [])
    update_query, rep_change = {}, 0
    if vote_type == 'upvote':
        if upvoted_by_user: update_query = {'$pull': {'upvotes': user_id_obj}}; rep_change = -points_for_upvote
        else: update_query = {'$addToSet': {'upvotes': user_id_obj}, '$pull': {'downvotes': user_id_obj}}; rep_change = points_for_upvote
        if downvoted_by_user and not upvoted_by_user: rep_change -= points_for_downvote
    elif vote_type == 'downvote':
        if downvoted_by_user: update_query = {'$pull': {'downvotes': user_id_obj}}; rep_change = -points_for_downvote if author_id != user_id_obj else -points_self_downvote
        else: update_query = {'$addToSet': {'downvotes': user_id_obj}, '$pull': {'upvotes': user_id_obj}}; rep_change = points_for_downvote if author_id != user_id_obj else points_self_downvote
        if upvoted_by_user and not downvoted_by_user: rep_change -= points_for_upvote
    if update_query:
        collection.update_one({'_id': item_id_obj}, update_query)
        if rep_change != 0:
            if author_id != user_id_obj: mongo.db.users.update_one({'_id': author_id}, {'$inc': {'reputation': rep_change}}); check_and_award_all_badges(author_id)
            elif author_id == user_id_obj and (vote_type == 'downvote' or (vote_type == 'upvote' and upvoted_by_user)): mongo.db.users.update_one({'_id': author_id}, {'$inc': {'reputation': rep_change}}); check_and_award_all_badges(author_id)
    updated_item = collection.find_one({'_id': item_id_obj})
    up_count, down_count = len(updated_item.get('upvotes', [])), len(updated_item.get('downvotes', []))
    return jsonify({'status': 'success', 'upvotes': up_count, 'downvotes': down_count, 'net_votes': up_count - down_count, 'message': 'Vote processed.'}), 200

# --- 8. Context Processors ---
@app.context_processor
def inject_global_vars():
    footer_contact_form = FooterContactForm()
    unread_notifications_count = 0
    level_info = None
    if current_user.is_authenticated:
        unread_notifications_count = mongo.db.notifications.count_documents({'recipient_id': ObjectId(current_user.id), 'is_read': False})
        level_info = get_level_info(current_user.reputation)
    return dict(now=datetime.now(timezone.utc), footer_form=footer_contact_form, unread_notifications_count=unread_notifications_count, BADGES_CONFIG_CTX=BADGES_CONFIG, current_user_level=level_info)

@app.context_processor
def utility_processor():
    def get_user_by_id(user_id_str):
        try: user_doc = mongo.db.users.find_one({'_id': ObjectId(user_id_str)}); return user_doc['username'] if user_doc else "Unknown User"
        except Exception: return "Unknown User"
    def get_question_title(question_id_str):
        try: question = mongo.db.questions.find_one({'_id': ObjectId(question_id_str)}, {'title': 1}); return question['title'] if question else "Question not found"
        except Exception: return "Question not found"
    
    def calculate_level(reputation):
        return get_level_info(reputation)

    return dict(get_user_by_id=get_user_by_id, get_question_title=get_question_title, calculate_level=calculate_level)

@app.template_filter('markdown')
def markdown_filter(text):
    if not text:
        return ""
    # Safe tags and attributes for bleach
    allowed_tags = bleach.sanitizer.ALLOWED_TAGS | {
        'p', 'br', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'pre', 'code',
        'span', 'div', 'blockquote', 'hr', 'ul', 'ol', 'li'
    }
    allowed_attrs = bleach.sanitizer.ALLOWED_ATTRIBUTES.copy()
    allowed_attrs.update({
        '*': ['class', 'style'],
        'code': ['class'],
    })
    
    # Convert markdown to HTML
    from markupsafe import Markup
    html = markdown.markdown(text, extensions=['fenced_code', 'codehilite', 'tables', 'nl2br'])
    # Sanitize HTML
    safe_html = bleach.clean(html, tags=allowed_tags, attributes=allowed_attrs)
    return Markup(safe_html)

# --- 9. Main Application Routes ---
@app.route('/')
def index():
    page, per_page = request.args.get('page', 1, type=int), 10
    questions_cursor = mongo.db.questions.find().sort('timestamp', -1).skip((page - 1) * per_page).limit(per_page)
    questions_with_details = []
    for q_doc in questions_cursor:
        author = mongo.db.users.find_one({'_id': q_doc['author_id']})
        q_doc.update({'author_username': author['username'] if author else 'Unknown', 'answers_count': mongo.db.answers.count_documents({'question_id': q_doc['_id']}), 'net_votes': len(q_doc.get('upvotes', [])) - len(q_doc.get('downvotes', []))})
        questions_with_details.append(q_doc)
    total_questions = mongo.db.questions.count_documents({})
    total_pages = (total_questions + per_page - 1) // per_page
    return render_template('index.html', questions=questions_with_details, page=page, total_pages=total_pages)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated: return redirect(url_for('index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        mongo.db.users.insert_one({'username': form.username.data, 'email': form.email.data, 'password_hash': hashed_password, 'reputation': 0, 'joined_date': datetime.now(timezone.utc), 'bio': '', 'role':'user'})
        flash('Account created! Please log in.', 'success'); return redirect(url_for('login'))
    return render_template('register.html', title='Register', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated: return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user_data = mongo.db.users.find_one({'email': form.email.data})
        if user_data and user_data.get('password_hash') and bcrypt.check_password_hash(user_data['password_hash'], form.password.data):
            login_user(User(user_data), remember=form.remember.data); next_page = request.args.get('next')
            flash('Login successful!', 'success'); return redirect(next_page) if next_page and next_page.startswith('/') else redirect(url_for('index'))
        else: flash('Login Unsuccessful. Check email/password or use social login.', 'danger')
    return render_template('login.html', title='Login', form=form)

@app.route('/logout')
@login_required
def logout(): logout_user(); flash('You have been logged out.', 'info'); return redirect(url_for('index'))

@app.route('/ask', methods=['GET', 'POST'])
@login_required
def ask_question():
    form = QuestionForm()
    if form.validate_on_submit():
        unique_tags = list(dict.fromkeys([tag.strip().lower() for tag in form.tags.data.split(',') if tag.strip()]))
        question_id = mongo.db.questions.insert_one({'title': form.title.data, 'body': form.body.data, 'tags': unique_tags, 'author_id': ObjectId(current_user.id), 'timestamp': datetime.now(timezone.utc), 'views': 0, 'upvotes': [], 'downvotes': [], 'best_answer_id': None}).inserted_id
        check_and_award_all_badges(ObjectId(current_user.id))
        flash('Your question has been posted!', 'success'); return redirect(url_for('view_question', question_id_str=str(question_id)))
    return render_template('ask_question.html', title='Ask a Question', form=form)

@app.route('/question/<question_id_str>', methods=['GET', 'POST'])
def view_question(question_id_str):
    try: q_id_obj = ObjectId(question_id_str)
    except Exception: flash('Invalid question ID.', 'danger'); return redirect(url_for('index'))
    question_doc = mongo.db.questions.find_one_and_update({'_id': q_id_obj}, {'$inc': {'views': 1}}, return_document=True)
    if not question_doc: flash('Question not found.', 'danger'); return redirect(url_for('index'))
    author = mongo.db.users.find_one({'_id': question_doc['author_id']})
    question_doc.update({'author_username': author['username'] if author else 'Unknown', 'author_reputation': author['reputation'] if author else 0, 'net_votes': len(question_doc.get('upvotes', [])) - len(question_doc.get('downvotes', []))})
    question_comments = []
    for c in mongo.db.comments.find({'parent_id': q_id_obj, 'parent_type': 'question'}).sort('timestamp', 1):
        ca = mongo.db.users.find_one({'_id': c['author_id']}, {'username': 1}); c.update({'author_username': ca['username'] if ca else 'Unknown', 'upvotes': c.get('upvotes', []), 'downvotes': c.get('downvotes', [])}); question_comments.append(c)
    question_doc['comments'] = question_comments
    answers_details = []
    for ad in mongo.db.answers.find({'question_id': q_id_obj}):
        aa = mongo.db.users.find_one({'_id': ad['author_id']}); ad.update({'author_username': aa['username'] if aa else 'Unknown', 'author_reputation': aa['reputation'] if aa else 0, 'net_votes': len(ad.get('upvotes', [])) - len(ad.get('downvotes', [])), 'is_best': (question_doc.get('best_answer_id') == ad['_id'])})
        ac_list = []
        for c in mongo.db.comments.find({'parent_id': ad['_id'], 'parent_type': 'answer'}).sort('timestamp', 1):
            ca = mongo.db.users.find_one({'_id': c['author_id']}, {'username': 1}); c.update({'author_username': ca['username'] if ca else 'Unknown', 'upvotes': c.get('upvotes', []), 'downvotes': c.get('downvotes', [])}); ac_list.append(c)
        ad['comments'] = ac_list; answers_details.append(ad)
    if question_doc.get('best_answer_id'): answers_details.sort(key=lambda x: (x['_id'] != question_doc['best_answer_id'], -x['net_votes'], x['timestamp']))
    else: answers_details.sort(key=lambda x: (-x['net_votes'], x['timestamp']))
    answer_form, comment_form = AnswerForm(), CommentForm()
    if answer_form.validate_on_submit() and current_user.is_authenticated:
        new_ans_id = mongo.db.answers.insert_one({'question_id': q_id_obj, 'author_id': ObjectId(current_user.id), 'body': answer_form.body.data, 'timestamp': datetime.now(timezone.utc), 'upvotes': [], 'downvotes': []}).inserted_id
        mongo.db.users.update_one({'_id': ObjectId(current_user.id)}, {'$inc': {'reputation': 2}})
        create_notification(question_doc['author_id'], ObjectId(current_user.id), 'new_answer', q_id_obj, new_ans_id)
        check_and_award_all_badges(ObjectId(current_user.id))
        flash('Answer posted!', 'success'); return redirect(url_for('view_question', question_id_str=question_id_str))
    elif answer_form.is_submitted() and not current_user.is_authenticated: flash('Login to post an answer.', 'warning')
    return render_template('view_question.html', title=question_doc['title'], question=question_doc, answers=answers_details, answer_form=answer_form, comment_form=comment_form)

@app.route('/profile/<username>')
def profile(username):
    user_data = mongo.db.users.find_one({'username': username})
    if not user_data: flash('User not found.', 'danger'); return redirect(url_for('index'))
    uid = user_data['_id']
    questions = []
    for q in mongo.db.questions.find({'author_id': uid}).sort('timestamp', -1): q.update({'answers_count': mongo.db.answers.count_documents({'question_id': q['_id']}), 'net_votes': len(q.get('upvotes',[]))-len(q.get('downvotes',[]))}); questions.append(q)
    answers = []
    for a in mongo.db.answers.find({'author_id': uid}).sort('timestamp', -1):
        q_title_doc = mongo.db.questions.find_one({'_id': a['question_id']}, {'title':1}); a.update({'question_title': q_title_doc['title'] if q_title_doc else 'N/A', 'question_id_str':str(a['question_id'])}); answers.append(a)
    badges = []
    for b_doc in mongo.db.user_badges.find({'user_id': uid}).sort('awarded_at', 1):
        b_info = BADGES_CONFIG.get(b_doc['badge_id']); 
        if b_info: badges.append({**b_info, 'badge_id':b_doc['badge_id'], 'awarded_at':b_doc['awarded_at']})
    return render_template('profile.html', title=f"{user_data['username']}'s Profile", user_profile=user_data, questions=questions, user_answers=answers, answers_count=len(answers), awarded_badges=badges)

@app.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    user_doc = mongo.db.users.find_one({'_id': ObjectId(current_user.id)})
    if not user_doc: flash('User not found.', 'danger'); return redirect(url_for('index'))
    form = EditProfileForm(user_doc['username'], user_doc['email'])
    if form.validate_on_submit():
        updates, changed = {}, False
        if form.username.data != user_doc['username']: updates['username'] = form.username.data; changed = True
        if form.email.data != user_doc['email']: updates['email'] = form.email.data; changed = True
        if form.bio.data != user_doc.get('bio',''): updates['bio'] = form.bio.data; changed = True; check_and_award_all_badges(ObjectId(current_user.id)) if form.bio.data.strip() else None
        if form.new_password.data:
            if not form.current_password.data: form.current_password.errors.append('Current password needed.')
            elif not user_doc.get('password_hash') or not bcrypt.check_password_hash(user_doc['password_hash'], form.current_password.data): form.current_password.errors.append('Incorrect current password.')
            else: updates['password_hash'] = bcrypt.generate_password_hash(form.new_password.data).decode('utf-8'); changed = True; flash('Password updated!', 'success')
        if form.errors: return render_template('edit_profile.html', title='Edit Profile', form=form, user_profile=user_doc) # Re-render with errors
        if updates:
            mongo.db.users.update_one({'_id': ObjectId(current_user.id)}, {'$set': updates})
            if 'username' in updates: current_user.username = updates['username']
            if 'email' in updates: current_user.email = updates['email']
            if 'bio' in updates: current_user.bio = updates['bio']
            if changed and not ('password_hash' in updates and len(updates) == 1): flash('Profile updated!', 'success')
        elif not changed and not form.new_password.data: flash('No changes submitted.', 'info')
        return redirect(url_for('profile', username=current_user.username))
    elif request.method == 'GET': form.username.data, form.email.data, form.bio.data = user_doc['username'], user_doc['email'], user_doc.get('bio','')
    return render_template('edit_profile.html', title='Edit Profile', form=form, user_profile=user_doc)

@app.route("/request_password_reset", methods=['GET', 'POST'])
def request_password_reset():
    if current_user.is_authenticated: return redirect(url_for('index'))
    form = RequestPasswordResetForm()
    if form.validate_on_submit():
        user_doc = mongo.db.users.find_one({'email': form.email.data})
        if user_doc and user_doc.get('password_hash'):
            token = s.dumps({'user_id': str(user_doc['_id'])}, salt=PASSWORD_RESET_SALT)
            if send_password_reset_email(user_doc['email'], token): flash('Password reset email sent.', 'info')
            else: flash('Error sending reset email. Try again later.', 'danger')
        else: flash('If account exists with local password, reset link sent.', 'info')
        return redirect(url_for('login'))
    return render_template('request_reset.html', title='Request Password Reset', form=form)

@app.route("/reset_password/<token>", methods=['GET', 'POST'])
def reset_token(token):
    if current_user.is_authenticated: return redirect(url_for('index'))
    try: user_id = s.loads(token, salt=PASSWORD_RESET_SALT, max_age=3600).get('user_id')
    except Exception: flash('Invalid/expired token.', 'warning'); return redirect(url_for('request_password_reset'))
    user_doc = mongo.db.users.find_one({'_id': ObjectId(user_id)})
    if not user_doc: flash('User not found for token.', 'warning'); return redirect(url_for('request_password_reset'))
    form = ResetPasswordForm()
    if form.validate_on_submit():
        mongo.db.users.update_one({'_id': ObjectId(user_id)}, {'$set': {'password_hash': bcrypt.generate_password_hash(form.password.data).decode('utf-8')}})
        flash('Password updated! You can now log in.', 'success'); return redirect(url_for('login'))
    return render_template('reset_token.html', title='Reset Your Password', form=form, token=token)

# --- Static Pages Route (for footer links) ---
@app.route('/pages/<page_name>')
def static_page(page_name):
    allowed_pages = ['faq', 'community-guidelines', 'terms-of-service', 'privacy-policy', 'about-us']
    if page_name in allowed_pages:
        try:
            page_title = page_name.replace('-', ' ').title()
            return render_template(f"static_pages/{page_name}.html", title=page_title)
        except TemplateNotFound:
            app.logger.error(f"Template not found: static_pages/{page_name}.html")
            abort(404)
    else:
        abort(404)

# --- Google OAuth Signal Handlers ---
@oauth_authorized.connect_via(google_bp)
def google_logged_in(blueprint, token):
    if not token: flash("Failed Google login.", "danger"); return redirect(url_for("login"))
    resp = blueprint.session.get("/oauth2/v3/userinfo")
    if not resp.ok: flash(f"Failed to fetch Google user info: {resp.status_code}", "danger"); return redirect(url_for("login"))
    info = resp.json()
    email, name, google_id = info.get("email"), info.get("name"), info.get("sub")
    if not email: flash("Google email not received.", "danger"); return redirect(url_for("login"))
    user_doc = mongo.db.users.find_one({"google_id": google_id})
    if not user_doc: user_doc = mongo.db.users.find_one({"email": email})
    if user_doc: 
        if not user_doc.get("google_id"): mongo.db.users.update_one({'_id': user_doc['_id']}, {'$set': {'google_id': google_id}}); user_doc['google_id'] = google_id
        login_user(User(user_doc)); flash("Logged in with Google!", "success")
    else: 
        base = "".join(filter(str.isalnum, name.split(" ")[0])).lower() if name else email.split('@')[0]
        uname, c = base or "user", 1
        while mongo.db.users.find_one({"username": uname}): uname = f"{base}{c}"; c += 1
        uid = mongo.db.users.insert_one({"email": email, "username": uname, "google_id": google_id, "password_hash": None, "role": "user", "joined_date": datetime.now(timezone.utc), "bio": "", "reputation": 0}).inserted_id
        newly_created_user_doc = mongo.db.users.find_one({'_id': uid})
        if newly_created_user_doc: login_user(User(newly_created_user_doc)); flash("Account created via Google!", "success")
        else: flash("Error creating account via Google.", "danger")
    check_and_award_all_badges(ObjectId(current_user.id)) # Check badges after social login/registration
    return redirect(url_for("index"))

@oauth_error.connect_via(google_bp)
def google_error(blueprint, error, error_description=None, error_uri=None):
    msg = f"OAuth error from {blueprint.name}: {error} desc: {error_description} uri: {error_uri}"
    app.logger.error(msg); flash("Google login failed. Try again or use regular login.", "danger"); return redirect(url_for("login"))

# --- API-like Routes ---
@app.route('/vote/question/<question_id_str>/<vote_type>', methods=['POST'])
@login_required
def vote_question(question_id_str, vote_type): return _handle_vote('questions', question_id_str, vote_type, 10, -2, -1)

@app.route('/vote/answer/<answer_id_str>/<vote_type>', methods=['POST'])
@login_required
def vote_answer(answer_id_str, vote_type): return _handle_vote('answers', answer_id_str, vote_type, 15, -3, -1)

@app.route('/vote/comment/<comment_id_str>/<vote_type>', methods=['POST'])
@login_required
def vote_comment(comment_id_str, vote_type): return _handle_vote('comments', comment_id_str, vote_type, 2, -1, 0)

@app.route('/question/<question_id_str>/mark_best_answer/<answer_id_str>', methods=['POST'])
@login_required
def mark_best_answer(question_id_str, answer_id_str):
    try: q_id_obj, ans_id_obj = ObjectId(question_id_str), ObjectId(answer_id_str)
    except Exception: return jsonify({'status': 'error', 'message': 'Invalid ID format.'}), 400
    question, answer = mongo.db.questions.find_one({'_id': q_id_obj}), mongo.db.answers.find_one({'_id': ans_id_obj, 'question_id': q_id_obj})
    if not (question and answer): return jsonify({'status': 'error', 'message': 'Question or Answer not found.'}), 404
    if question['author_id'] != ObjectId(current_user.id): return jsonify({'status': 'error', 'message': 'Only the question author can mark a best answer.'}), 403
    points_best_ans = 25
    if question.get('best_answer_id') and question['best_answer_id'] != ans_id_obj:
        prev_best_ans_doc = mongo.db.answers.find_one({'_id': question['best_answer_id']})
        if prev_best_ans_doc: mongo.db.users.update_one({'_id': prev_best_ans_doc['author_id']}, {'$inc': {'reputation': -points_best_ans}})
    mongo.db.questions.update_one({'_id': q_id_obj}, {'$set': {'best_answer_id': ans_id_obj}})
    mongo.db.users.update_one({'_id': answer['author_id']}, {'$inc': {'reputation': points_best_ans}})
    create_notification(recipient_id=answer['author_id'], actor_id=ObjectId(current_user.id), action_type='best_answer', target_id=q_id_obj, reference_id=ans_id_obj)
    check_and_award_all_badges(answer['author_id'])
    return jsonify({'status': 'success', 'message': 'Best answer marked.', 'best_answer_id': str(ans_id_obj)}), 200

@app.route('/comment/add/<parent_type>/<parent_id_str>', methods=['POST'])
@login_required
def add_comment(parent_type, parent_id_str):
    if parent_type not in ['question', 'answer']: return jsonify({'status': 'error', 'message': 'Invalid parent type.'}), 400
    try: parent_id_obj = ObjectId(parent_id_str)
    except Exception: return jsonify({'status': 'error', 'message': 'Invalid parent ID format.'}), 400
    comment_body = request.form.get('body', '').strip()
    if not comment_body or len(comment_body) < 3 or len(comment_body) > 500: return jsonify({'status': 'error', 'message': 'Comment must be 3-500 characters.'}), 400
    comment_doc = {'parent_id': parent_id_obj, 'parent_type': parent_type, 'author_id': ObjectId(current_user.id), 'body': comment_body, 'timestamp': datetime.now(timezone.utc), 'upvotes': [], 'downvotes': []}
    try:
        comment_id = mongo.db.comments.insert_one(comment_doc).inserted_id
        author_info = mongo.db.users.find_one({'_id': ObjectId(current_user.id)}, {'username': 1})
        parent_item_author_id, notif_action_type, target_parent_id_for_notif = None, None, None
        if parent_type == 'question':
            question = mongo.db.questions.find_one({'_id': parent_id_obj}, {'author_id': 1});
            if question: parent_item_author_id = question['author_id']
            notif_action_type = 'new_comment_on_question'
        elif parent_type == 'answer':
            answer = mongo.db.answers.find_one({'_id': parent_id_obj}, {'author_id': 1, 'question_id': 1})
            if answer: parent_item_author_id = answer['author_id']; target_parent_id_for_notif = answer['question_id']
            notif_action_type = 'new_comment_on_answer'
        if parent_item_author_id and notif_action_type:
            create_notification(recipient_id=parent_item_author_id, actor_id=ObjectId(current_user.id), action_type=notif_action_type, target_id=parent_id_obj, reference_id=comment_id, target_parent_id=target_parent_id_for_notif)
        complete_comment_data = {**comment_doc, '_id': comment_id, 'author_username': author_info['username'] if author_info else 'Unknown'}
        rendered_comment_html = render_template('partials/_comment.html', comment=complete_comment_data)
        return jsonify({'status': 'success', 'message': 'Comment posted!', 'comment_html': rendered_comment_html, 'parent_id_str': parent_id_str, 'parent_type': parent_type}), 200
    except Exception as e: app.logger.error(f"Error saving comment: {e}"); return jsonify({'status': 'error', 'message': 'Could not save comment.'}), 500

@app.route('/comment/edit/<comment_id_str>', methods=['POST'])
@login_required
def edit_comment(comment_id_str):
    try: comment_id_obj = ObjectId(comment_id_str)
    except Exception: return jsonify({'status': 'error', 'message': 'Invalid comment ID.'}), 400
    comment = mongo.db.comments.find_one({'_id': comment_id_obj})
    if not comment: return jsonify({'status': 'error', 'message': 'Comment not found.'}), 404
    if comment['author_id'] != ObjectId(current_user.id) and not getattr(current_user, 'is_admin', False): return jsonify({'status': 'error', 'message': 'Not authorized.'}), 403 # Allow admin to edit
    new_body = request.form.get('body', '').strip()
    if not new_body or len(new_body) < 3 or len(new_body) > 500: return jsonify({'status': 'error', 'message': 'Comment length invalid.'}), 400
    mongo.db.comments.update_one({'_id': comment_id_obj}, {'$set': {'body': new_body, 'edited_timestamp': datetime.now(timezone.utc)}})
    return jsonify({'status': 'success', 'message': 'Comment updated.', 'new_body': new_body}), 200

@app.route('/comment/delete/<comment_id_str>', methods=['POST'])
@login_required
def delete_comment(comment_id_str):
    try: comment_id_obj = ObjectId(comment_id_str)
    except Exception: return jsonify({'status': 'error', 'message': 'Invalid comment ID.'}), 400
    comment = mongo.db.comments.find_one({'_id': comment_id_obj})
    if not comment: return jsonify({'status': 'error', 'message': 'Comment not found.'}), 404
    is_admin = getattr(current_user, 'is_admin', False)
    if comment['author_id'] != ObjectId(current_user.id) and not is_admin: return jsonify({'status': 'error', 'message': 'Not authorized.'}), 403
    mongo.db.comments.delete_one({'_id': comment_id_obj})
    return jsonify({'status': 'success', 'message': 'Comment deleted.'}), 200

@app.route('/submit-feedback', methods=['POST'])
def submit_feedback():
    form = FooterContactForm(request.form)
    if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        if form.validate():
            email, message = form.email.data, form.message.data
            try: mongo.db.feedback.insert_one({'email': email, 'message': message, 'timestamp': datetime.now(timezone.utc), 'user_id': ObjectId(current_user.id) if current_user.is_authenticated else None})
            except Exception as e: app.logger.error(f"Error saving feedback: {e}"); return jsonify({'status': 'error', 'message': 'Could not save feedback.'}), 500
            return jsonify({'status': 'success', 'message': 'Thank you for your feedback!'}), 200
        else: errors = {field: error[0] for field, error in form.errors.items()}; return jsonify({'status': 'error', 'message': 'Validation failed.', 'errors': errors}), 400
    else:
        if form.validate_on_submit(): flash('Thank you for your feedback!', 'success')
        else:
            for field, errors_list in form.errors.items():
                for error_msg in errors_list: flash(f"Error in {getattr(form, field).label.text}: {error_msg}", 'danger')
        return redirect(request.referrer + '#footer-contact-form' if request.referrer else url_for('index'))

@app.route('/search')
def search_results():
    query_string = request.args.get('query', '').strip()
    tag_query = request.args.get('tag', '').strip().lower()
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    # Get filter parameters
    selected_tags = request.args.getlist('tags')
    date_range = request.args.get('date_range', '')
    status = request.args.get('status', '')
    min_votes = request.args.get('min_votes', type=int)
    sort_by = request.args.get('sort', 'newest')
    
    # Build search filter
    search_filter = {}
    
    # Text search
    if query_string:
        regex_query = re.compile(query_string, re.IGNORECASE)
        search_filter['$or'] = [
            {'title': {'$regex': regex_query}},
            {'body': {'$regex': regex_query}}
        ]
    
    # Tag filter
    if tag_query:
        search_filter['tags'] = tag_query
    elif selected_tags:
        search_filter['tags'] = {'$in': selected_tags}
    
    # Date range filter
    if date_range:
        now = datetime.now(timezone.utc)
        if date_range == 'today':
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif date_range == 'week':
            start_date = now - timedelta(days=7)
        elif date_range == 'month':
            start_date = now - timedelta(days=30)
        elif date_range == 'year':
            start_date = now - timedelta(days=365)
        else:
            start_date = None
        
        if start_date:
            search_filter['timestamp'] = {'$gte': start_date}
    
    # Answer status filter
    if status == 'answered':
        # Questions with at least one answer
        answered_questions = mongo.db.answers.distinct('question_id')
        search_filter['_id'] = {'$in': answered_questions}
    elif status == 'unanswered':
        # Questions with no answers
        answered_questions = mongo.db.answers.distinct('question_id')
        search_filter['_id'] = {'$nin': answered_questions}
    elif status == 'accepted':
        # Questions with accepted answer
        search_filter['best_answer_id'] = {'$ne': None}
    
    # Get questions
    questions_cursor = mongo.db.questions.find(search_filter)
    
    # Sort
    if sort_by == 'newest':
        questions_cursor = questions_cursor.sort('timestamp', -1)
    elif sort_by == 'votes':
        # Sort by net votes (will calculate in Python)
        pass
    elif sort_by == 'views':
        questions_cursor = questions_cursor.sort('views', -1)
    elif sort_by == 'active':
        # Sort by last activity (timestamp for now, could track last answer time)
        questions_cursor = questions_cursor.sort('timestamp', -1)
    
    # Process questions
    questions_with_details = []
    for q_doc in questions_cursor:
        author = mongo.db.users.find_one({'_id': q_doc['author_id']})
        net_votes = len(q_doc.get('upvotes', [])) - len(q_doc.get('downvotes', []))
        
        # Apply min votes filter
        if min_votes is not None and net_votes < min_votes:
            continue
        
        q_doc.update({
            'author_username': author['username'] if author else 'Unknown',
            'answers_count': mongo.db.answers.count_documents({'question_id': q_doc['_id']}),
            'net_votes': net_votes
        })
        questions_with_details.append(q_doc)
    
    # Sort by votes if needed (after calculating net_votes)
    if sort_by == 'votes':
        questions_with_details.sort(key=lambda x: x['net_votes'], reverse=True)
    
    # Pagination
    total_questions = len(questions_with_details)
    total_pages = (total_questions + per_page - 1) // per_page
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    questions_with_details = questions_with_details[start_idx:end_idx]
    
    # Get popular tags for filter
    popular_tags = mongo.db.questions.aggregate([
        {'$unwind': '$tags'},
        {'$group': {'_id': '$tags', 'count': {'$sum': 1}}},
        {'$sort': {'count': -1}},
        {'$limit': 15}
    ])
    popular_tags = [tag['_id'] for tag in popular_tags]
    
    # Build filter params for URL
    filter_params = {}
    if selected_tags:
        filter_params['tags'] = selected_tags
    if date_range:
        filter_params['date_range'] = date_range
    if status:
        filter_params['status'] = status
    if min_votes:
        filter_params['min_votes'] = min_votes
    
    return render_template('search_results.html',
                         questions=questions_with_details,
                         query=query_string,
                         tag=tag_query,
                         page=page,
                         total_pages=total_pages,
                         total_results=total_questions,
                         popular_tags=popular_tags,
                         selected_tags=selected_tags,
                         date_range=date_range,
                         status=status,
                         min_votes=min_votes,
                         sort_by=sort_by,
                         filter_params=filter_params)


# --- API Routes ---
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

# --- Notification Routes ---
@app.route('/notifications')
@login_required
def view_notifications_page():
    notifications_cursor = mongo.db.notifications.find({'recipient_id': ObjectId(current_user.id)}).sort('timestamp', -1).limit(30)
    notifications_list = []
    for notif in notifications_cursor:
        actor = mongo.db.users.find_one({'_id': notif['actor_id']}, {'username': 1})
        notif['actor_username'] = actor['username'] if actor else 'Someone'
        message, target_link, item_text = f"<strong>{notif['actor_username']}</strong> ", "#", ""
        ref_id_str, target_id_str = str(notif.get('reference_id', '')), str(notif.get('target_id', ''))
        target_parent_id_str = str(notif.get('target_parent_id', '')) if notif.get('target_parent_id') else None
        if notif['action_type'] == 'new_comment_on_question':
            q = mongo.db.questions.find_one({'_id': ObjectId(target_id_str)}, {'title': 1}) if ObjectId.is_valid(target_id_str) else None
            item_text = f"your question: \"{q['title'][:40]}...\"" if q else "your question"
            message += f"commented on {item_text}."; target_link = url_for('view_question', question_id_str=target_id_str, _anchor=f"comment-{ref_id_str}")
        elif notif['action_type'] == 'new_comment_on_answer':
            q_title = "a question"
            if target_parent_id_str and ObjectId.is_valid(target_parent_id_str):
                q = mongo.db.questions.find_one({'_id': ObjectId(target_parent_id_str)}, {'title': 1})
                if q: q_title = f"\"{q['title'][:40]}...\""
            item_text = f"your answer on {q_title}"; message += f"commented on {item_text}."
            target_link = url_for('view_question', question_id_str=target_parent_id_str, _anchor=f"comment-{ref_id_str}") if target_parent_id_str else "#"
        elif notif['action_type'] == 'new_answer':
            q = mongo.db.questions.find_one({'_id': ObjectId(target_id_str)}, {'title': 1}) if ObjectId.is_valid(target_id_str) else None
            item_text = f"your question: \"{q['title'][:40]}...\"" if q else "your question"
            message += f"answered {item_text}."; target_link = url_for('view_question', question_id_str=target_id_str, _anchor=f"answer-{ref_id_str}")
        elif notif['action_type'] == 'best_answer':
            q = mongo.db.questions.find_one({'_id': ObjectId(target_id_str)}, {'title': 1}) if ObjectId.is_valid(target_id_str) else None
            q_title = f"\"{q['title'][:40]}...\"" if q else "a question"
            message += f"marked your answer as best for {q_title}."; target_link = url_for('view_question', question_id_str=target_id_str, _anchor=f"answer-{ref_id_str}")
        elif notif['action_type'] == 'new_badge':
            badge_id = notif.get('reference_id')
            badge_config = BADGES_CONFIG.get(badge_id, {})
            badge_name = badge_config.get('name', 'a new badge')
            message = f"Congratulations! You've earned the <strong>'{badge_name}'</strong> badge."
            target_link = url_for('profile', username=notif['actor_username'], _anchor="profile-badges-section")
            notif['badge_icon_class'] = badge_config.get('icon_class', 'fas fa-medal')
            notif['badge_icon_color'] = badge_config.get('icon_color', 'var(--secondary-color)')
        notif.update({'human_readable_message': message, 'target_link': target_link}); notifications_list.append(notif)
    return render_template('notifications.html', title="Your Notifications", notifications=notifications_list)

@app.route('/notifications/mark_read/<notification_id_str>', methods=['POST'])
@login_required
def mark_notification_as_read(notification_id_str):
    try:
        notif_id_obj = ObjectId(notification_id_str)
        result = mongo.db.notifications.update_one({'_id': notif_id_obj, 'recipient_id': ObjectId(current_user.id)}, {'$set': {'is_read': True}})
        new_unread_count = mongo.db.notifications.count_documents({'recipient_id': ObjectId(current_user.id), 'is_read': False})
        if result.modified_count > 0: return jsonify({'status': 'success', 'message': 'Notification marked as read.', 'new_unread_count': new_unread_count})
        return jsonify({'status': 'info', 'message': 'Already read or not found.', 'new_unread_count': new_unread_count}), 200
    except Exception as e: app.logger.error(f"Error marking notification read: {e}"); return jsonify({'status': 'error', 'message': 'Could not mark as read.'}), 500

@app.route('/notifications/mark_all_read', methods=['POST'])
@login_required
def mark_all_notifications_as_read():
    try:
        mongo.db.notifications.update_many({'recipient_id': ObjectId(current_user.id), 'is_read': False}, {'$set': {'is_read': True}})
        return jsonify({'status': 'success', 'message': 'All notifications marked as read.', 'new_unread_count': 0})
    except Exception as e: app.logger.error(f"Error marking all notifications read: {e}"); return jsonify({'status': 'error', 'message': 'Could not mark all as read.'}), 500



# --- 11. Error Handlers ---
@app.errorhandler(404)
def page_not_found(e): return render_template('errors/404.html', title="Page Not Found"), 404
@app.errorhandler(500)
def internal_server_error(e): app.logger.error(f"Server Error: {e}", exc_info=True); return render_template('errors/500.html', title="Internal Server Error"), 500

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


# --- 12. Main Execution ---
if __name__ == '__main__':
    import logging
    logging.basicConfig(level=logging.INFO)
    app.logger.info("Starting Hikmat Hub application...")
    app.run(debug=True, port=5001)
