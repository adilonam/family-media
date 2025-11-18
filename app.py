from flask import Flask, render_template, request, jsonify
import database_manager as dbm

# Initialize the Flask app
app = Flask(__name__)

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
            results = [
                {
                    "id": file[0],
                    "name": file[1],
                    "path": file[2],
                    "description": file[3]
                }
                for file in files
            ]
            return jsonify(results)
    
        except Exception as e:
            conn.close()
            return jsonify({"error": str(e)}), 500
            
    return jsonify({"error": "Could not connect to database"}), 500

# --- 3. Add File API Route ---
@app.route('/addfile', methods=['POST'])
def add_file_route():
    """
    This route handles adding a new file.
    It expects data sent from an HTML form.
    
    NOTE: This basic example doesn't handle the *actual file upload*.
    It only adds the metadata (the file info and tags) to the database.
    """
    # Get data from the submitted form
    file_name = request.form.get('filename')
    file_path = request.form.get('filepath')
    description = request.form.get('description')
    tags_string = request.form.get('tags') # e.g., "Vacation, Beach, 2025"

    if not file_name or not file_path or not tags_string:
        return jsonify({"error": "Missing required fields"}), 400

    conn = dbm.create_connection()
    if conn:
        try:
            # Add the file to the Files table
            new_file_id = dbm.add_file(
                conn,
                file_name=file_name,
                file_path=file_path,
                file_type="Unknown", # You can enhance this later
                mime_type="Unknown", # You can enhance this later
                description=description
            )
            
            if new_file_id:
                # Add the tags
                tags_list = [tag.strip() for tag in tags_string.split(',')]
                for tag in tags_list:
                    if tag: # Ensure tag is not empty
                        dbm.link_file_to_tag(conn, new_file_id, tag)
            
            conn.close()
            return jsonify({"success": f"File '{file_name}' added with ID {new_file_id}"})
    
        except Exception as e:
            conn.close()
            return jsonify({"error": str(e)}), 500

    return jsonify({"error": "Could not connect to database"}), 500


# --- Run the App ---
if __name__ == '__main__':
    # This makes the server accessible on your local machine
    # Go to http://127.0.0.1:5000 or http://localhost:5000 in your browser
    app.run(debug=True, port=5000)
