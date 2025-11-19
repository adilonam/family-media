import sqlite3
import os

DATABASE_FILE = "family.db"


def create_connection():
    """Create a database connection to the SQLite database."""
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        # Enable foreign key support
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn
    except sqlite3.Error as e:
        print(f"Error connecting to database: {e}")
    return conn


def create_tables(conn):
    """Create the necessary tables if they don't exist."""
    sql_create_files_table = """
    CREATE TABLE IF NOT EXISTS Files (
        FileID INTEGER PRIMARY KEY AUTOINCREMENT,
        FileName TEXT NOT NULL,
        FilePath TEXT NOT NULL UNIQUE,
        ThumbnailPath TEXT,
        FileType TEXT,
        MIMEType TEXT,
        DateAdded TEXT DEFAULT CURRENT_TIMESTAMP,
        Description TEXT
    );
    """
    
    sql_create_tags_table = """
    CREATE TABLE IF NOT EXISTS Tags (
        TagID INTEGER PRIMARY KEY AUTOINCREMENT,
        TagName TEXT NOT NULL UNIQUE
    );
    """
    
    sql_create_link_table = """
    CREATE TABLE IF NOT EXISTS FileTags_Link (
        FileID INTEGER NOT NULL,
        TagID INTEGER NOT NULL,
        PRIMARY KEY (FileID, TagID),
        FOREIGN KEY (FileID) REFERENCES Files (FileID) ON DELETE CASCADE,
        FOREIGN KEY (TagID) REFERENCES Tags (TagID) ON DELETE CASCADE
    );
    """
    
    try:
        c = conn.cursor()
        c.execute(sql_create_files_table)
        c.execute(sql_create_tags_table)
        c.execute(sql_create_link_table)
        conn.commit()
    except sqlite3.Error as e:
        print(f"Error creating tables: {e}")


def add_file(conn, file_name, file_path, file_type, mime_type, description="", thumbnail_path=None):
    """
    Add a new file to the Files table.
    Returns the FileID of the newly added file.
    """
    sql = ''' INSERT INTO Files(FileName, FilePath, FileType, MIMEType, Description, ThumbnailPath)
              VALUES(?,?,?,?,?,?) '''
    try:
        cur = conn.cursor()
        cur.execute(sql, (file_name, file_path, file_type, mime_type, description, thumbnail_path))
        conn.commit()
        return cur.lastrowid
    except sqlite3.IntegrityError:
        print(f"Error: File path '{file_path}' already exists in the database.")
        return None
    except sqlite3.Error as e:
        print(f"Error adding file: {e}")
        return None


def add_tag(conn, tag_name):
    """
    Add a new tag to the Tags table if it doesn't already exist.
    Returns the TagID.
    """
    # First, try to get the tag if it exists
    cur = conn.cursor()
    cur.execute("SELECT TagID FROM Tags WHERE TagName = ?", (tag_name,))
    data = cur.fetchone()
    
    if data:
        # Tag already exists, return its ID
        return data[0]
    else:
        # Tag doesn't exist, insert it
        sql = ''' INSERT INTO Tags(TagName) VALUES(?) '''
        try:
            cur.execute(sql, (tag_name,))
            conn.commit()
            return cur.lastrowid
        except sqlite3.Error as e:
            print(f"Error adding tag: {e}")
            return None


def link_file_to_tag(conn, file_id, tag_name):
    """
    Link a file to a tag.
    This will create the tag if it doesn't exist.
    """
    # Get or create the tag ID
    tag_id = add_tag(conn, tag_name)
    
    if file_id is None or tag_id is None:
        print("Error: Invalid FileID or TagID.")
        return
    
    sql = ''' INSERT INTO FileTags_Link(FileID, TagID) VALUES(?,?) '''
    try:
        cur = conn.cursor()
        cur.execute(sql, (file_id, tag_id))
        conn.commit()
        print(f"Linked FileID {file_id} to Tag '{tag_name}' (TagID {tag_id})")
    except sqlite3.IntegrityError:
        # This link already exists, which is fine
        pass
    except sqlite3.Error as e:
        print(f"Error linking file and tag: {e}")


def search_files_by_tag(conn, tag_name):
    """
    Find all files associated with a given tag name.
    """
    sql = """
    SELECT
        Files.FileID,
        Files.FileName,
        Files.FilePath,
        Files.Description,
        Files.ThumbnailPath
    FROM Files
    JOIN FileTags_Link ON Files.FileID = FileTags_Link.FileID
    JOIN Tags ON FileTags_Link.TagID = Tags.TagID
    WHERE Tags.TagName = ?
    """
    
    try:
        cur = conn.cursor()
        cur.execute(sql, (tag_name,))
        rows = cur.fetchall()
        return rows
    except sqlite3.Error as e:
        print(f"Error searching by tag: {e}")
        return []


# --- Main execution example ---
if __name__ == "__main__":
    # This block runs only when you execute the script directly
    
    # 1. Create connection and tables
    conn = create_connection()
    if conn:
        create_tables(conn)
        print("Database and tables created successfully (if they didn't exist).")
        
        # 2. Add some example files
        file1_id = add_file(conn, 
                           file_name="beach_trip_2025_01.jpg",
                           file_path="/FamilyDatabase/Images/beach_trip_2025_01.jpg",
                           file_type="Image",
                           mime_type="image/jpeg",
                           description="Fun day at the beach")
        
        file2_id = add_file(conn,
                           file_name="grandmas_recipe.docx",
                           file_path="/FamilyDatabase/Documents/grandmas_recipe.docx",
                           file_type="Document",
                           mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                           description="Grandma's secret cookie recipe")
        
        # 3. Link files to tags
        if file1_id:
            link_file_to_tag(conn, file1_id, "Vacation")
            link_file_to_tag(conn, file1_id, "Beach")
            link_file_to_tag(conn, file1_id, "2025")
        
        if file2_id:
            link_file_to_tag(conn, file2_id, "Family")
            link_file_to_tag(conn, file2_id, "Recipes")
        
        # 4. Search for files
        print("\n--- Searching for 'Vacation' files ---")
        vacation_files = search_files_by_tag(conn, "Vacation")
        if vacation_files:
            for file in vacation_files:
                print(f"  Found: {file}")
        else:
            print("  No files found for 'Vacation'.")
        
        print("\n--- Searching for 'Recipes' files ---")
        recipe_files = search_files_by_tag(conn, "Recipes")
        if recipe_files:
            for file in recipe_files:
                print(f"  Found: {file}")
        else:
            print("  No files found for 'Recipes'.")
        
        # Close the connection
        conn.close()
        print("\nExample finished and connection closed.")

