import os
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# Enforce secure session key configurations in cloud runtimes
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'surplus_to_service_secret_key_change_in_production')

# ─── RAILWAY COMPATIBLE DATABASE URI CONFIGURATION ────────────────────
LOCAL_MYSQL_URI = 'mysql+pymysql://root:Smbsmb%402007@localhost:3306/surplus_service'
# Railway uses 'MYSQL_URL' for its managed database installations. 
# We fall back to DATABASE_URL or your local instance configuration.
raw_db_url = os.environ.get('MYSQL_URL') or os.environ.get('DATABASE_URL') or LOCAL_MYSQL_URI

# SQLAlchemy requires explicit drivers. We ensure 'mysql://' expands out to use 'mysql+pymysql://'
if raw_db_url and raw_db_url.startswith('mysql://'):
    raw_db_url = raw_db_url.replace('mysql://', 'mysql+pymysql://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = raw_db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

ROLE_CATEGORY_MAPPING = {
    "Farmer": "Produce",
    "Restaurant": "Meals",
    "NGO": "Organic Waste",
    "Composter": "Fertilizer"
}

# ─── MODELS ────────────────────────────────────────────────────────────

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Handled cascading deletes natively via ORM relationships safely
    listings = db.relationship('Listing', backref='author_node', cascade="all, delete-orphan", lazy=True)

class Listing(db.Model):
    __tablename__ = 'listings'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text, nullable=False)
    weight = db.Column(db.Float, default=0.0)
    pickup_info = db.Column(db.String(200), default="Available for pickup")
    status = db.Column(db.String(50), default="available")  # States: available, claimed, completed
    location_name = db.Column(db.String(100), default="Main Hub")
    address = db.Column(db.String(200), default="Default Address")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

with app.app_context():
    db.create_all()

# ─── HELPERS / DECORATORS ──────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please sign in to access this page.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        if not session.get('is_admin'):
            flash('Admin access required.', 'danger')
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated

# ─── AUTH ROUTES ───────────────────────────────────────────────────────

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return redirect(url_for('home'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('home'))
        
    if request.method == 'POST':
        identifier = request.form.get('email') or request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=identifier).first()
        
        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            session['user_name'] = user.username
            session['user_role'] = user.role
            session['user_email'] = user.email
            session['is_admin'] = user.is_admin
            flash(f'Welcome back, {user.username}!', 'success')
            return redirect(url_for('home'))
            
        flash('Invalid credentials.', 'danger')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('home'))
        
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        role = request.form.get('role', '').strip()

        if not all([username, email, password, role]):
            flash('Please complete all fields.', 'danger')
            return render_template('register.html')

        if User.query.filter_by(email=email).first():
            flash('An account with this email already exists.', 'danger')
            return render_template('register.html')

        hashed_pw = generate_password_hash(password)
        new_user = User(username=username, email=email, password_hash=hashed_pw, role=role)
        db.session.add(new_user)
        db.session.commit()
        
        flash('Account created successfully! Please sign in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been signed out.', 'success')
    return redirect(url_for('login'))

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        if email:
            flash('If this email exists, a recovery link has been sent.', 'success')
            return redirect(url_for('login'))
        flash('Please provide a valid email.', 'danger')
    return render_template('forgot_password.html')

# ─── MAIN PLATFORM ROUTES ──────────────────────────────────────────────

@app.route('/home')
@login_required
def home():
    recent_listings = Listing.query.filter_by(status='available').order_by(Listing.id.desc()).limit(6).all()
    total_exchanges = Listing.query.filter(Listing.status.in_(['claimed', 'completed'])).count()
    
    saved_weight = db.session.query(db.func.sum(Listing.weight)).filter_by(status='completed').scalar()
    food_saved = float(saved_weight) if saved_weight else 0.0
    total_nodes = User.query.count()
    
    return render_template('home.html',
                           recent=recent_listings,
                           total_exchanges=total_exchanges,
                           food_saved=round(food_saved, 1),
                           total_nodes=total_nodes,
                           co2_saved=round(food_saved * 2.3, 1))

@app.route('/browse')
@login_required
def browse():
    search = request.args.get('search', '').strip()
    category_filter = request.args.get('category', 'all')
    query = Listing.query.filter_by(status='available')
    
    if category_filter != 'all':
        query = query.filter_by(category=category_filter)
    if search:
        query = query.filter(Listing.title.ilike(f'%{search}%') | Listing.description.ilike(f'%{search}%'))
        
    listings = query.order_by(Listing.id.desc()).all()
    return render_template('browse.html', listings=listings, current_category=category_filter, search=search)

@app.route('/post', methods=['GET', 'POST'])
@login_required
def post():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        category = request.form.get('category', '').strip()
        description = request.form.get('description', '').strip()
        weight = float(request.form.get('weight', 0.0) or 0.0)
        pickup_info = request.form.get('pickup_info', 'Pick up anytime')
        location_name = request.form.get('location_name', 'Main Office')
        address = request.form.get('address', 'Ecosystem Center')
        
        if title and category and description:
            new_listing = Listing(
                title=title, category=category, description=description,
                weight=weight, pickup_info=pickup_info,
                location_name=location_name, address=address,
                status="available", user_id=session['user_id']
            )
            db.session.add(new_listing)
            db.session.commit()
            flash('Listing published successfully!', 'success')
            return redirect(url_for('browse'))
            
        flash('Please fill in all required fields.', 'danger')
    return render_template('post.html')

@app.route('/listing/<int:listing_id>')
@login_required
def listing_detail(listing_id):
    listing = Listing.query.get_or_404(listing_id)
    return render_template('listing_detail.html', listing=listing)

@app.route('/claim/<int:listing_id>', methods=['POST'])
@login_required
def claim(listing_id):
    listing = Listing.query.get_or_404(listing_id)
    if listing.status != 'available':
        flash('This listing is no longer available.', 'danger')
        return redirect(url_for('browse'))
        
    listing.status = 'claimed'
    db.session.commit()
    flash('Resource successfully claimed!', 'success')
    return redirect(url_for('confirmed', listing_id=listing_id))

@app.route('/confirmed/<int:listing_id>')
@login_required
def confirmed(listing_id):
    listing = Listing.query.get_or_404(listing_id)
    return render_template('confirmed.html', listing=listing, timestamp=datetime.utcnow())

@app.route('/dashboard')
@login_required
def dashboard():
    user_id = session['user_id']
    exchanges = Listing.query.filter_by(user_id=user_id).order_by(Listing.id.desc()).all()
    total_posted = len(exchanges)
    active_listings = Listing.query.filter_by(user_id=user_id, status='available').count()
    
    saved_weight = db.session.query(db.func.sum(Listing.weight)).filter_by(user_id=user_id, status='completed').scalar()
    saved_metric = float(saved_weight) if saved_weight else 0.0
    user = User.query.get(user_id)
    
    return render_template('dashboard.html',
                           exchanges=exchanges, total=total_posted,
                           saved=round(saved_metric, 1),
                           co2=round(saved_metric * 2.3, 1),
                           active_listings=active_listings, user=user)

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    user = User.query.get(session['user_id'])
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        role = request.form.get('role', '').strip()
        new_password = request.form.get('new_password', '').strip()
        
        if username:
            user.username = username
            session['user_name'] = username
        if role:
            user.role = role
            session['user_role'] = role
        if new_password:
            user.password_hash = generate_password_hash(new_password)
            
        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('profile'))
    return render_template('profile.html', user=user)

@app.route('/complete/<int:exchange_id>')
@login_required
def complete_exchange(exchange_id):
    listing = Listing.query.get_or_404(exchange_id)
    listing.status = 'completed'
    db.session.commit()
    flash('Exchange marked as completed!', 'success')
    return redirect(url_for('dashboard'))

# ─── ADMIN ROUTES ──────────────────────────────────────────────────────

@app.route('/admin')
@admin_required
def admin_panel():
    total_users = User.query.count()
    total_listings = Listing.query.count()
    active_listings = Listing.query.filter_by(status='available').count()
    completed = Listing.query.filter_by(status='completed').count()
    
    users = User.query.order_by(User.created_at.desc()).all()
    listings = Listing.query.order_by(Listing.id.desc()).all()
    
    return render_template('admin/panel.html',
                           total_users=total_users,
                           total_listings=total_listings,
                           active_listings=active_listings,
                           completed=completed,
                           users=users, listings=listings)

@app.route('/admin/delete-user/<int:user_id>', methods=['POST'])
@admin_required
def admin_delete_user(user_id):
    user = User.query.get_or_404(user_id)
    # The ORM cascading option deletes all nested user listings automatically
    db.session.delete(user)
    db.session.commit()
    flash('User and all associated listings deleted.', 'success')
    return redirect(url_for('admin_panel'))

@app.route('/admin/delete-listing/<int:listing_id>', methods=['POST'])
@admin_required
def admin_delete_listing(listing_id):
    listing = Listing.query.get_or_404(listing_id)
    db.session.delete(listing)
    db.session.commit()
    flash('Listing deleted.', 'success')
    return redirect(url_for('admin_panel'))

@app.route('/admin/make-admin/<int:user_id>', methods=['POST'])
@admin_required
def make_admin(user_id):
    user = User.query.get_or_404(user_id)
    user.is_admin = True
    db.session.commit()
    flash(f'{user.username} is now an admin.', 'success')
    return redirect(url_for('admin_panel'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
