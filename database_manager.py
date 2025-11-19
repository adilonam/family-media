import sqlite3
import os
# Import password hashing tools
from werkzeug.security import generate_password_hash, check_password_hash

DATABASE_FILE = "family.db"


def create_connection():
    """Create a database connection to the SQLite database."""
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn
    except sqlite3.Error as e:
        print(f"Error connecting to database: {e}")
    return conn


def create_tables(conn):
    """Create all tables for the application."""
    try:
        c = conn.cursor()
        
        # --- Files Table (Unchanged, but added for completeness) ---
        c.execute("""
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
        """)

        # --- NEW: Users Table ---
        c.execute("""
        CREATE TABLE IF NOT EXISTS Users (
            UserID INTEGER PRIMARY KEY AUTOINCREMENT,
            Username TEXT NOT NULL UNIQUE,
            PasswordHash TEXT NOT NULL
        );
        """)
        
        # --- MODIFIED: Tags Table (Added IsPublic) ---
        c.execute("""
        CREATE TABLE IF NOT EXISTS Tags (
            TagID INTEGER PRIMARY KEY AUTOINCREMENT,
            TagName TEXT NOT NULL UNIQUE,
            IsPublic INTEGER DEFAULT 1 NOT NULL
        );
        """)
        
        # --- FileTags_Link Table (Unchanged) ---
        c.execute("""
        CREATE TABLE IF NOT EXISTS FileTags_Link (
            FileID INTEGER NOT NULL,
            TagID INTEGER NOT NULL,
            PRIMARY KEY (FileID, TagID),
            FOREIGN KEY (FileID) REFERENCES Files (FileID) ON DELETE CASCADE,
            FOREIGN KEY (TagID) REFERENCES Tags (TagID) ON DELETE CASCADE
        );
        """)
        
        # --- NEW: UserTagPermissions Table ---
        # This links a user to a private tag
        c.execute("""
        CREATE TABLE IF NOT EXISTS UserTagPermissions (
            UserID INTEGER NOT NULL,
            TagID INTEGER NOT NULL,
            PRIMARY KEY (UserID, TagID),
            FOREIGN KEY (UserID) REFERENCES Users (UserID) ON DELETE CASCADE,
            FOREIGN KEY (TagID) REFERENCES Tags (TagID) ON DELETE CASCADE
        );
        """)
        
        conn.commit()
    except sqlite3.Error as e:
        print(f"Error creating tables: {e}")


# --- File and Tag Functions ---

def add_file(conn, file_name, file_path, file_type, mime_type, description="", thumbnail_path=None):
    sql = ''' INSERT INTO Files(FileName, FilePath, FileType, MIMEType, Description, ThumbnailPath)
              VALUES(?,?,?,?,?,?) '''
    try:
        cur = conn.cursor()
        cur.execute(sql, (file_name, file_path, file_type, mime_type, description, thumbnail_path))
        conn.commit()
        return cur.lastrowid
    except sqlite3.IntegrityError:
        return None  # File path already exists
    except sqlite3.Error as e:
        print(f"Error adding file: {e}")
        return None


def add_tag(conn, tag_name, is_public=True):
    """
    Add a new tag. Returns the TagID.
    """
    cur = conn.cursor()
    cur.execute("SELECT TagID FROM Tags WHERE TagName = ?", (tag_name,))
    data = cur.fetchone()
    
    if data:
        return data[0]  # Tag already exists
    else:
        sql = ''' INSERT INTO Tags(TagName, IsPublic) VALUES(?,?) '''
        try:
            is_public_int = 1 if is_public else 0
            cur.execute(sql, (tag_name, is_public_int))
            conn.commit()
            return cur.lastrowid
        except sqlite3.Error as e:
            print(f"Error adding tag: {e}")
            return None


def link_file_to_tag(conn, file_id, tag_id):
    sql = ''' INSERT INTO FileTags_Link(FileID, TagID) VALUES(?,?) '''
    try:
        cur = conn.cursor()
        cur.execute(sql, (file_id, tag_id))
        conn.commit()
    except sqlite3.IntegrityError:
        pass  # Link already exists
    except sqlite3.Error as e:
        print(f"Error linking file and tag: {e}")


# --- NEW: User and Permission Functions ---

def create_user(conn, username, password):
    """Create a new user with a hashed password."""
    sql = ''' INSERT INTO Users(Username, PasswordHash) VALUES(?,?) '''
    try:
        hashed_password = generate_password_hash(password)
        cur = conn.cursor()
        cur.execute(sql, (username, hashed_password))
        conn.commit()
        return cur.lastrowid
    except sqlite3.IntegrityError:
        return None  # Username already exists
    except sqlite3.Error as e:
        print(f"Error creating user: {e}")
        return None


def get_user_by_name(conn, username):
    """Query a user by username."""
    cur = conn.cursor()
    cur.execute("SELECT * FROM Users WHERE Username = ?", (username,))
    return cur.fetchone()


def get_user_by_id(conn, user_id):
    """Query a user by user ID."""
    cur = conn.cursor()
    cur.execute("SELECT * FROM Users WHERE UserID = ?", (user_id,))
    return cur.fetchone()


def check_password(password_hash, password):
    """Check a stored password hash against a new password."""
    return check_password_hash(password_hash, password)


def link_user_to_tag(conn, user_id, tag_id):
    """Give a user permission for a private tag."""
    sql = ''' INSERT INTO UserTagPermissions(UserID, TagID) VALUES(?,?) '''
    try:
        cur = conn.cursor()
        cur.execute(sql, (user_id, tag_id))
        conn.commit()
    except sqlite3.IntegrityError:
        pass  # Permission already exists
    except sqlite3.Error as e:
        print(f"Error linking user and tag: {e}")


def search_files_by_tag_for_user(conn, tag_name, user_id):
    """
    Find files for a tag, checking if the user has permission.
    """
    sql = """
    SELECT
        Files.FileID, Files.FileName, Files.FilePath, Files.Description, Files.ThumbnailPath
    FROM Files
    JOIN FileTags_Link ON Files.FileID = FileTags_Link.FileID
    JOIN Tags ON FileTags_Link.TagID = Tags.TagID
    LEFT JOIN UserTagPermissions ON Tags.TagID = UserTagPermissions.TagID
    WHERE 
        Tags.TagName = ?
        AND (Tags.IsPublic = 1 OR UserTagPermissions.UserID = ?)
    """
    try:
        cur = conn.cursor()
        cur.execute(sql, (tag_name, user_id))
        return cur.fetchall()
    except sqlite3.Error as e:
        print(f"Error searching by tag: {e}")
        return []


# --- Main execution example ---
if __name__ == "__main__":
    conn = create_connection()
    if conn:
        create_tables(conn)
        print("Database and tables created.")
        
        # Create a test user
        user_id = create_user(conn, "admin", "password123")
        if user_id:
            print(f"Created user 'admin' with ID {user_id}")
        else:
            print("User 'admin' may already exist.")
        
        conn.close()
