from flask import Flask, request, jsonify
import uuid
import os
from datetime import datetime, timedelta
import sqlite3

app = Flask(__name__)

# Database bestand (Render behoudt dit tijdens runtime)
DB_PATH = "/tmp/keys.db"

def get_db():
    """Maakt verbinding met SQLite database"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Maakt de tabel aan als die niet bestaat"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS licenses (
            key TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            expires TEXT,
            created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            active INTEGER DEFAULT 1,
            uses INTEGER DEFAULT 0
        )
    ''')
    
    conn.commit()
    conn.close()

def generate_key():
    """Genereert unieke key"""
    return '-'.join([uuid.uuid4().hex[:4].upper() for _ in range(4)])

@app.route('/')
def home():
    """Check hoeveel keys er zijn"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM licenses')
        count = cursor.fetchone()[0]
        conn.close()
        return f"Auth Server Running! Totaal keys: {count}"
    except Exception as e:
        return f"Server running, DB error: {str(e)}"

@app.route('/create', methods=['POST'])
def create_key():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "Geen data"}), 400
            
        name = data.get("name")
        key_type = data.get("type", "1m")
        
        if not name:
            return jsonify({"success": False, "error": "Naam verplicht"}), 400
        
        # Genereer key
        key = generate_key()
        
        # Bepaal vervaldatum
        if key_type == "1m":
            expires = (datetime.now() + timedelta(days=30)).isoformat()
        elif key_type == "3m":
            expires = (datetime.now() + timedelta(days=90)).isoformat()
        else:
            expires = "never"
        
        # Sla op in database
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO licenses (key, name, type, expires, active, uses)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (key, name, key_type, expires, 1, 0))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            "success": True,
            "key": key,
            "type": key_type,
            "expires": expires
        })
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/validate', methods=['POST'])
def validate_key():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"valid": False}), 400
            
        key = data.get("key")
        if not key:
            return jsonify({"valid": False}), 400
        
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM licenses WHERE key = ?', (key,))
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return jsonify({"valid": False, "reason": "not_found"})
        
        license_data = dict(row)
        
        if not license_data['active']:
            conn.close()
            return jsonify({"valid": False, "reason": "inactive"})
        
        expires = license_data['expires']
        
        # Check lifetime
        if expires == "never":
            cursor.execute('UPDATE licenses SET uses = uses + 1 WHERE key = ?', (key,))
            conn.commit()
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
                cursor.execute('UPDATE licenses SET uses = uses + 1 WHERE key = ?', (key,))
                conn.commit()
                conn.close()
                return jsonify({
                    "valid": True,
                    "expires": expires,
                    "name": license_data['name']
                })
            else:
                conn.close()
                return jsonify({"valid": False, "reason": "expired"})
        except:
            conn.close()
            return jsonify({"valid": False})
            
    except Exception as e:
        return jsonify({"valid": False, "error": str(e)}), 500

@app.route('/list')
def list_keys():
    """Laat alle keys zien"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM licenses ORDER BY created DESC')
        rows = cursor.fetchall()
        
        keys = []
        for row in rows:
            keys.append({
                "key": row['key'],
                "name": row['name'],
                "type": row['type'],
                "expires": row['expires'],
                "created": row['created'],
                "active": bool(row['active']),
                "uses": row['uses']
            })
        
        conn.close()
        return jsonify(keys)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/delete/<key>', methods=['DELETE'])
def delete_key(key):
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM licenses WHERE key = ?', (key,))
        
        if cursor.rowcount == 0:
            conn.close()
            return jsonify({"success": False, "error": "Niet gevonden"})
        
        conn.commit()
        conn.close()
        
        return jsonify({"success": True, "message": f"Key {key} verwijderd"})
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# Start database bij opstarten
try:
    init_db()
    print("SQLite database geinitialiseerd!")
except Exception as e:
    print(f"Database fout: {e}")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
