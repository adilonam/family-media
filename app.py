from flask import (
    Flask, render_template, request, jsonify, send_from_directory, 
    url_for, redirect, flash
)
# Import Flask-Login
from flask_login import (
    LoginManager, UserMixin, login_user, logout_user, 
    login_required, current_user
)
# Import Flask-WTF forms
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, EqualTo, ValidationError

import database_manager as dbm
import os
from werkzeug.utils import secure_filename
from PIL import Image

# --- App and Folder Config ---
UPLOAD_FOLDER = os.path.join(os.getcwd(), 'FamilyFileVault')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(__name__)
# We MUST set a secret key for sessions and forms
app.config['SECRET_KEY'] = 'a-very-secret-and-random-string-change-this' 
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# --- 1. Flask-Login Configuration ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'  # Redirect to '/login' if user is not logged in
login_manager.login_message = 'You must be logged in to access this page.'

class User(UserMixin):
    """User model for Flask-Login."""
    def __init__(self, user_id, username):
        self.id = user_id
        self.username = username

@login_manager.user_loader
def load_user(user_id):
    """Callback to reload the user object from the session."""
    conn = dbm.create_connection()
    user_data = dbm.get_user_by_id(conn, user_id)
    conn.close()
    if user_data:
        # user_data[0] is ID, user_data[1] is Username
        return User(user_data[0], user_data[1])
    return None

# --- 2. Form Classes (using Flask-WTF) ---

class LoginForm(FlaskForm):
    """Login form."""
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class RegistrationForm(FlaskForm):
    """Registration form."""
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    password2 = PasswordField(
        'Repeat Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Register')

    def validate_username(self, username):
        conn = dbm.create_connection()
        user = dbm.get_user_by_name(conn, username.data)
        conn.close()
        if user:
            raise ValidationError('That username is already taken.')

# --- 3. Authentication Routes (NEW) ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = LoginForm()
    if form.validate_on_submit():
        conn = dbm.create_connection()
        user_data = dbm.get_user_by_name(conn, form.username.data)
        conn.close()
        
        # user_data[2] is the PasswordHash
        if user_data and dbm.check_password(user_data[2], form.password.data):
            user = User(user_data[0], user_data[1])
            login_user(user)
            # Redirect to the page they were trying to access
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))
        else:
            flash('Login Unsuccessful. Please check username and password.', 'danger')
            
    return render_template('login.html', title='Login', form=form)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
        
    form = RegistrationForm()
    if form.validate_on_submit():
        conn = dbm.create_connection()
        user_id = dbm.create_user(conn, form.username.data, form.password.data)
        conn.close()
        if user_id:
            flash(f'Account created for {form.username.data}! You can now log in.', 'success')
            return redirect(url_for('login'))
        else:
            flash('Account creation failed.', 'danger')
            
    return render_template('register.html', title='Register', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# --- 4. Main Application Routes (MODIFIED) ---

@app.route('/')
@login_required  # Protect this page
def index():
    return render_template('index.html')

@app.route('/files/<path:filename>')
@login_required  # Protect files
def serve_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/search')
@login_required  # Protect search
def search():
    tag_query = request.args.get('tag')
    if not tag_query:
        return jsonify({"error": "No tag provided"}), 400

    conn = dbm.create_connection()
    if conn:
        try:
            # Use the NEW permission-checking search function
            files = dbm.search_files_by_tag_for_user(conn, tag_query, current_user.id)
            conn.close()
            
            results = []
            for file in files:  # file[0]=ID, [1]=Name, [3]=Desc, [4]=ThumbPath
                thumbnail_url = None
                if file[4]:  # If ThumbnailPath is not None
                    thumb_name = os.path.basename(file[4])
                    thumbnail_url = url_for('serve_file', filename=thumb_name)
                
                results.append({
                    "id": file[0],
                    "name": file[1],
                    "description": file[3],
                    "url": url_for('serve_file', filename=file[1]),
                    "thumbnail_url": thumbnail_url
                })
            return jsonify(results)
        except Exception as e:
            conn.close()
            return jsonify({"error": str(e)}), 500
            
    return jsonify({"error": "Could not connect to database"}), 500

@app.route('/addfile', methods=['POST'])
@login_required  # Protect uploading
def add_file_route():
    if 'file' not in request.files:
        return jsonify({"error": "No file part in the request"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    # Get metadata from the form
    description = request.form.get('description', '')
    tags_string = request.form.get('tags', '')
    # NEW: Check if tags should be private
    is_private = request.form.get('is_private') == 'true'

    if not tags_string:
        return jsonify({"error": "Tags are required"}), 400

    filename = secure_filename(file.filename)
    save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

    if os.path.exists(save_path):
        return jsonify({"error": f"File '{filename}' already exists."}), 400

    thumbnail_save_path = None
    conn = None  # Define conn outside try block
    
    try:
        file.save(save_path)  # Save original
        
        # --- Thumbnail ---
        mime_type = file.content_type if hasattr(file, 'content_type') else 'application/octet-stream'
        if mime_type and mime_type.startswith('image/'):
            try:
                thumbnail_filename = f"thumb_{filename}"
                thumbnail_save_path = os.path.join(app.config['UPLOAD_FOLDER'], thumbnail_filename)
                with Image.open(save_path) as im:
                    im.thumbnail((200, 200))
                    im.save(thumbnail_save_path)
            except Exception as e:
                print(f"Warning: Could not create thumbnail. {e}")
                thumbnail_save_path = None
        
        # --- Database ---
        conn = dbm.create_connection()
        if not conn:
            raise Exception("Could not connect to database")

        file_type = filename.split('.')[-1].upper() if '.' in filename else 'Unknown'
        
        new_file_id = dbm.add_file(
            conn, filename, save_path, file_type, 
            mime_type, description, thumbnail_save_path
        )
        
        if new_file_id:
            # --- Tag and Permission Logic ---
            tags_list = [tag.strip() for tag in tags_string.split(',')]
            for tag_name in tags_list:
                if tag_name:
                    # Add tag, respecting the 'is_private' flag
                    tag_id = dbm.add_tag(conn, tag_name, is_public=(not is_private))
                    
                    if tag_id:
                        # Link file to tag
                        dbm.link_file_to_tag(conn, new_file_id, tag_id)
                        
                        # If tag is private, link user to tag
                        if is_private:
                            dbm.link_user_to_tag(conn, current_user.id, tag_id)
        
        conn.close()
        return jsonify({"success": f"File '{filename}' uploaded and added."})

    except Exception as e:
        # Clean up
        if os.path.exists(save_path):
            os.remove(save_path)
        if thumbnail_save_path and os.path.exists(thumbnail_save_path):
            os.remove(thumbnail_save_path)
        if conn:
            conn.close()
        return jsonify({"error": str(e)}), 500

# --- Run the App ---
if __name__ == '__main__':
    # Run a quick check to create tables
    db_conn = dbm.create_connection()
    if db_conn:
        dbm.create_tables(db_conn)
        print("Database tables checked/created.")
        db_conn.close()
        
    app.run(debug=True, host='0.0.0.0', port=5000)
