from flask import render_template, url_for, flash, redirect, request, Blueprint, abort
from flask_login import login_user, current_user, logout_user, login_required
from . import db, bcrypt
from .models import User, Post, Comment
from sqlalchemy import func

main = Blueprint('main', __name__)

# Helper: pagination
def paginate(query, page, per_page=5):
    total = query.count()
    items = query.offset((page-1)*per_page).limit(per_page).all()
    pages = (total + per_page - 1)//per_page
    return {
        'items': items,
        'total': total,
        'page': page,
        'per_page': per_page,
        'pages': pages,
        'has_prev': page > 1,
        'has_next': page < pages,
        'prev_num': page - 1 if page > 1 else None,
        'next_num': page + 1 if page < pages else None
    }

# Home / Posts feed
@main.route('/')
@main.route('/home')
def home():
    page = request.args.get('page', 1, type=int)
    q = Post.query.order_by(Post.date_posted.desc())
    p = paginate(q, page, per_page=5)
    return render_template('index.html', posts=p['items'], p=p)

@main.route('/posts')
def posts():
    page = request.args.get('page', 1, type=int)
    q = Post.query.order_by(Post.date_posted.desc())
    p = paginate(q, page, per_page=5)
    return render_template('index.html', posts=p['items'], p=p)

# Register
@main.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.home'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        if not username or not password:
            flash('Username and password are required.', 'danger')
            return redirect(url_for('main.register'))
        # Case-insensitive uniqueness check
        if User.query.filter(func.lower(User.username) == username.lower()).first():
            flash('Username already taken. Please choose another.', 'warning')
            return redirect(url_for('main.register'))
        user = User(username=username)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash('Registration successful! You can now log in.', 'success')
        return redirect(url_for('main.login'))
    return render_template('register.html')

# Login
@main.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.home'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        # Case-insensitive user lookup
        user = User.query.filter(func.lower(User.username) == username.lower()).first()
        if user and user.check_password(password):
            login_user(user)
            flash('Logged in successfully.', 'success')
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('main.home'))
        else:
            flash('Login failed. Check username and password.', 'danger')
    return render_template('login.html')

# Logout
@main.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out successfully.', 'success')
    return redirect(url_for('main.home'))

# Dashboard
@main.route('/dashboard')
@login_required
def dashboard():
    page = request.args.get('page', 1, type=int)
    q = Post.query.filter_by(author=current_user).order_by(Post.date_posted.desc())
    p = paginate(q, page, per_page=5)
    return render_template('dashboard.html', my_posts=p['items'], p=p, username=current_user.username)

# Create post
@main.route('/post/new', methods=['GET', 'POST'])
@login_required
def new_post():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        content = request.form.get('content', '').strip()
        if not title or not content:
            flash('Title and content are required.', 'danger')
            return redirect(url_for('main.new_post'))
        post = Post(title=title, content=content, author=current_user)
        db.session.add(post)
        db.session.commit()
        flash('Post created!', 'success')
        return redirect(url_for('main.post_detail', post_id=post.id))
    return render_template('new_post.html')

# Edit post (owner only)
@main.route('/post/<int:post_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post.author != current_user:
        abort(403)
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        content = request.form.get('content', '').strip()
        if not title or not content:
            flash('Title and content are required.', 'danger')
            return redirect(url_for('main.edit_post', post_id=post.id))
        post.title = title
        post.content = content
        db.session.commit()
        flash('Post updated.', 'success')
        return redirect(url_for('main.post_detail', post_id=post.id))
    return render_template('edit_post.html', post=post)

# Delete post (owner only)
@main.route('/post/<int:post_id>/delete', methods=['POST'])
@login_required
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post.author != current_user:
        abort(403)

    # Safety: manual cascade for legacy DBs
    Comment.query.filter_by(post_id=post.id).delete(synchronize_session=False)

    db.session.delete(post)
    db.session.commit()
    flash('Post deleted.', 'success')
    return redirect(url_for('main.dashboard'))

# Post detail + comments
@main.route('/post/<int:post_id>', methods=['GET', 'POST'])
def post_detail(post_id):
    post = Post.query.get_or_404(post_id)

    # Handle new comment
    if request.method == 'POST':
        if not current_user.is_authenticated:
            flash('Please log in to comment.', 'info')
            return redirect(url_for('main.login', next=url_for('main.post_detail', post_id=post.id)))
        content = request.form.get('comment_content', '').strip()
        if not content:
            flash('Comment cannot be empty.', 'warning')
            return redirect(url_for('main.post_detail', post_id=post.id))
        comment = Comment(content=content, commenter=current_user, post=post)
        db.session.add(comment)
        db.session.commit()
        flash('Your comment has been added.', 'success')
        return redirect(url_for('main.post_detail', post_id=post.id))

    comments = Comment.query.filter_by(post=post).order_by(Comment.date_commented.desc()).all()
    return render_template('post_detail.html', post=post, comments=comments)
