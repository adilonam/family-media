from flask import Flask, render_template, request, jsonify, send_from_directory, url_for
import database_manager as dbm
import os
from werkzeug.utils import secure_filename
from PIL import Image

# --- Configuration ---
# Define the path where files will be saved
UPLOAD_FOLDER = os.path.join(os.getcwd(), 'FamilyFileVault')
# Create the folder if it doesn't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Initialize the Flask app
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Initialize database tables on startup
def init_db():
    """Initialize the database and create tables if they don't exist."""
    conn = dbm.create_connection()
    if conn:
        dbm.create_tables(conn)
        conn.close()

# Create tables when the app starts
init_db()

# --- 1. Main Page Route ---
@app.route('/')
def index():
    """
    This route serves your main HTML page ('index.html').
    """
    # 'render_template' looks inside the 'templates' folder
    return render_template('index.html')

# --- 2. Search API Route (MODIFIED) ---
@app.route('/search')
def search():
    """
    This route now returns a usable URL for each file.
    It expects a 'tag' in the URL, like: /search?tag=Vacation
    """
    tag_query = request.args.get('tag')
    if not tag_query:
        return jsonify({"error": "No tag provided"}), 400

    conn = dbm.create_connection()
    if conn:
        try:
            files = dbm.search_files_by_tag(conn, tag_query)
            conn.close()
            results = []
            for file in files:
                # file[4] is the ThumbnailPath
                thumbnail_url = None
                if file[4]:  # If ThumbnailPath is not None
                    # Get just the filename (e.g., "thumb_beach.jpg")
                    thumb_name = os.path.basename(file[4])
                    thumbnail_url = url_for('serve_file', filename=thumb_name)
                
                results.append({
                    "id": file[0],
                    "name": file[1],
                    "description": file[3],
                    "url": url_for('serve_file', filename=file[1]),
                    "thumbnail_url": thumbnail_url  # <--- ADD THE NEW URL
                })
            return jsonify(results)
        
        except Exception as e:
            conn.close()
            return jsonify({"error": str(e)}), 500
            
    return jsonify({"error": "Could not connect to database"}), 500

# --- 4. Add File API Route ---
@app.route('/addfile', methods=['POST'])
def add_file_route():
    """
    This route now handles file uploads and metadata.
    """
    # Check if a file was part of the request
    if 'file' not in request.files:
        return jsonify({"error": "No file part in the request"}), 400
    
    file = request.files['file']

    # If the user does not select a file, the browser submits an
    # empty file without a filename.
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    # Get metadata from the form
    description = request.form.get('description', '')
    tags_string = request.form.get('tags', '')

    if not tags_string:
        return jsonify({"error": "Tags are required"}), 400

    if file:
        # Secure the filename against directory traversal attacks
        filename = secure_filename(file.filename)
        
        # Create the full, absolute path to save the file
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

        # Check if file already exists (optional, but good practice)
        if os.path.exists(save_path):
            return jsonify({"error": f"File '{filename}' already exists."}), 400

        # --- New Thumbnail Variables ---
        thumbnail_save_path = None
        thumbnail_filename = None

        conn = None
        try:
            # --- 1. Save the actual file ---
            file.save(save_path)

            # --- Thumbnail Generation Logic ---
            mime_type = file.content_type if hasattr(file, 'content_type') else 'application/octet-stream'
            if mime_type and mime_type.startswith('image/'):
                try:
                    thumbnail_filename = f"thumb_{filename}"
                    thumbnail_save_path = os.path.join(app.config['UPLOAD_FOLDER'], thumbnail_filename)
                    
                    # Open the saved image, create a thumbnail, and save it
                    with Image.open(save_path) as im:
                        im.thumbnail((200, 200))  # Max size 200x200
                        im.save(thumbnail_save_path)
                    print(f"Thumbnail created at: {thumbnail_save_path}")
                except Exception as e:
                    print(f"Warning: Could not create thumbnail. {e}")
                    thumbnail_save_path = None  # Failed, so set back to None
            # --- End Thumbnail Logic ---
            
            # --- 2. Add metadata to database ---
            conn = dbm.create_connection()
            if not conn:
                # If database connection fails, try to delete the file we just saved
                if os.path.exists(save_path):
                    os.remove(save_path)
                if thumbnail_save_path and os.path.exists(thumbnail_save_path):
                    os.remove(thumbnail_save_path)
                return jsonify({"error": "Could not connect to database"}), 500

            file_type = filename.split('.')[-1].upper() if '.' in filename else 'Unknown'

            # --- Pass the thumbnail path to the database ---
            new_file_id = dbm.add_file(
                conn,
                file_name=filename,
                file_path=save_path, # Store the *actual save path*
                file_type=file_type,
                mime_type=mime_type,
                description=description,
                thumbnail_path=thumbnail_save_path  # Pass the new path
            )
            
            if new_file_id:
                # Add the tags
                tags_list = [tag.strip() for tag in tags_string.split(',')]
                for tag in tags_list:
                    if tag:
                        dbm.link_file_to_tag(conn, new_file_id, tag)
            
            conn.close()
            return jsonify({"success": f"File '{filename}' uploaded and added with ID {new_file_id}"})

        except Exception as e:
            # Clean up if something went wrong
            if os.path.exists(save_path):
                os.remove(save_path)
            if thumbnail_save_path and os.path.exists(thumbnail_save_path):
                os.remove(thumbnail_save_path)  # Also remove the thumbnail
            if conn:
                conn.close()
            return jsonify({"error": str(e)}), 500

    return jsonify({"error": "An unknown error occurred"}), 500

# --- 3. NEW Route to Serve Files ---
@app.route('/files/<path:filename>')
def serve_file(filename):
    """
    This new route securely serves files from your UPLOAD_FOLDER.
    """
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


# --- Run the App ---
if __name__ == '__main__':
    # This makes the server accessible on all network interfaces
    # Go to http://127.0.0.1:5000 or http://localhost:5000 in your browser
    app.run(debug=True, host='0.0.0.0', port=5000)
