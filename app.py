from flask import Flask, request, jsonify
import uuid
import os
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)

# Database URL van Render (zet dit in Environment Variables)
DATABASE_URL = os.environ.get('https://dashboard.render.com/d/dpg-d6otdn75gffc738pho5g-a/info')

def get_db_connection():
    """Maakt verbinding met PostgreSQL"""
    conn = psycopg2.connect(DATABASE_URL)
    return conn

def init_db():
    """Maakt de tabel aan als die niet bestaat"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS licenses (
            key VARCHAR(20) PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            type VARCHAR(10) NOT NULL,
            expires VARCHAR(50),
            created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            active BOOLEAN DEFAULT TRUE,
            uses INTEGER DEFAULT 0
        )
    ''')
    
    conn.commit()
    cur.close()
    conn.close()

@app.route('/')
def home():
    """Check of database werkt"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('SELECT COUNT(*) FROM licenses')
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
        return f"Auth Server Running! Totaal keys: {count}"
    except Exception as e:
        return f"Server running, DB error: {str(e)}"

# Admin: Maak nieuwe key
@app.route('/create', methods=['POST'])
def create_key():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No JSON data"}), 400
            
        name = data.get("name")
        key_type = data.get("type", "1m")
        
        if not name:
            return jsonify({"success": False, "error": "Name required"}), 400
        
        # Genereer unieke key
        key = '-'.join([uuid.uuid4().hex[:4].upper() for _ in range(4)])
        
        # Bepaal vervaldatum
        if key_type == "1m":
            expires = datetime.now() + timedelta(days=30)
            expires_str = expires.isoformat()
        elif key_type == "3m":
            expires = datetime.now() + timedelta(days=90)
            expires_str = expires.isoformat()
        else:  # lifetime
            expires_str = "never"
        
        # Sla op in database
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute('''
            INSERT INTO licenses (key, name, type, expires, active, uses)
            VALUES (%s, %s, %s, %s, %s, %s)
        ''', (key, name, key_type, expires_str, True, 0))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({
            "success": True,
            "key": key,
            "type": key_type,
            "expires": expires_str,
            "message": "Key opgeslagen in database"
        })
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# Client: Check of key geldig is
@app.route('/validate', methods=['POST'])
def validate_key():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"valid": False, "error": "No data"}), 400
            
        key = data.get("key")
        
        if not key:
            return jsonify({"valid": False, "error": "No key provided"}), 400
        
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute('SELECT * FROM licenses WHERE key = %s', (key,))
        license_data = cur.fetchone()
        
        if not license_data:
            cur.close()
            conn.close()
            return jsonify({"valid": False, "reason": "not_found"})
        
        if not license_data['active']:
            cur.close()
            conn.close()
            return jsonify({"valid": False, "reason": "inactive"})
        
        expires = license_data['expires']
        
        # Check lifetime
        if expires == "never":
            cur.execute('UPDATE licenses SET uses = uses + 1 WHERE key = %s', (key,))
            conn.commit()
            cur.close()
            conn.close()
            return jsonify({
                "valid": True, 
                "expires": "Lifetime", 
                "name": license_data['name']
            })
        
        # Check vervaldatum
        try:
            expire_date = datetime.fromisoformat(expires)
            if datetime.now() < expire_date:
                cur.execute('UPDATE licenses SET uses = uses + 1 WHERE key = %s', (key,))
                conn.commit()
                cur.close()
                conn.close()
                return jsonify({
                    "valid": True, 
                    "expires": expires, 
                    "name": license_data['name']
                })
            else:
                cur.close()
                conn.close()
                return jsonify({"valid": False, "reason": "expired"})
        except Exception as e:
            cur.close()
            conn.close()
            return jsonify({"valid": False, "reason": "date_error", "error": str(e)})
        
    except Exception as e:
        return jsonify({"valid": False, "error": str(e)}), 500

# Admin: Lijst van alle keys
@app.route('/list')
def list_keys():
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute('SELECT * FROM licenses ORDER BY created DESC')
        keys = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return jsonify([dict(row) for row in keys])
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Admin: Verwijder key
@app.route('/delete/<key>', methods=['DELETE'])
def delete_key(key):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute('DELETE FROM licenses WHERE key = %s', (key,))
        
        if cur.rowcount == 0:
            cur.close()
            conn.close()
            return jsonify({"success": False, "error": "Key not found"})
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({"success": True, "message": f"Key {key} verwijderd"})
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# Admin: Deactiveer key (in plaats van verwijderen)
@app.route('/deactivate/<key>', methods=['POST'])
def deactivate_key(key):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute('UPDATE licenses SET active = FALSE WHERE key = %s', (key,))
        
        if cur.rowcount == 0:
            cur.close()
            conn.close()
            return jsonify({"success": False, "error": "Key not found"})
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({"success": True, "message": f"Key {key} gedeactiveerd"})
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# Start database bij opstarten
with app.app_context():
    try:
        init_db()
        print("Database geinitialiseerd!")
    except Exception as e:
        print(f"Database fout: {e}")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
