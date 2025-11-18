from flask import Flask, render_template, request, jsonify, send_from_directory
import database_manager as dbm
import os
from werkzeug.utils import secure_filename

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

# --- 2. Search API Route ---
@app.route('/search')
def search():
    """
    This route responds to search requests from the webpage.
    It expects a 'tag' in the URL, like: /search?tag=Vacation
    """
    # Get the 'tag' from the URL parameters
    tag_query = request.args.get('tag')
    
    if not tag_query:
        return jsonify({"error": "No tag provided"}), 400

    conn = dbm.create_connection()
    if conn:
        try:
            files = dbm.search_files_by_tag(conn, tag_query)
            conn.close()
            
            # 'jsonify' turns the Python list of results into a format
            # the web browser can understand.
            # We'll format the results as a list of dictionaries.
            results = []
            for file in files:
                file_path = file[2]
                # Extract just the filename from the full path for the download link
                filename = os.path.basename(file_path)
                results.append({
                    "id": file[0],
                    "name": file[1],
                    "path": file_path,
                    "filename": filename,  # Add filename for download link
                    "description": file[3]
                })
            return jsonify(results)
    
        except Exception as e:
            conn.close()
            return jsonify({"error": str(e)}), 500
            
    return jsonify({"error": "Could not connect to database"}), 500

# --- 3. Add File API Route (MODIFIED) ---
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

        conn = None
        try:
            # --- 1. Save the actual file ---
            file.save(save_path)
            
            # --- 2. Add metadata to database ---
            conn = dbm.create_connection()
            if not conn:
                # If database connection fails, try to delete the file we just saved
                if os.path.exists(save_path):
                    os.remove(save_path)
                return jsonify({"error": "Could not connect to database"}), 500

            # Get file type and MIME type
            file_type = filename.split('.')[-1].upper() if '.' in filename else 'Unknown'
            mime_type = getattr(file, 'content_type', None) or 'application/octet-stream'

            new_file_id = dbm.add_file(
                conn,
                file_name=filename,
                file_path=save_path, # Store the *actual save path*
                file_type=file_type,
                mime_type=mime_type,
                description=description
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
            # If database insert fails, try to delete the file we just saved
            if os.path.exists(save_path):
                os.remove(save_path)
            if conn:
                conn.close()
            return jsonify({"error": str(e)}), 500

    return jsonify({"error": "An unknown error occurred"}), 500

# --- 4. Serve Files Route ---
@app.route('/files/<filename>')
def serve_file(filename):
    """
    Safely serve files from the UPLOAD_FOLDER.
    This allows the file paths in search results to be clickable links.
    """
    # Use secure_filename to prevent directory traversal attacks
    safe_filename = secure_filename(filename)
    return send_from_directory(app.config['UPLOAD_FOLDER'], safe_filename)


# --- Run the App ---
if __name__ == '__main__':
    # This makes the server accessible on your local machine
    # Go to http://127.0.0.1:5000 or http://localhost:5000 in your browser
    app.run(debug=True, port=5000)
