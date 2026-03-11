from flask import Flask, request, jsonify
import uuid
import json
import os
from datetime import datetime, timedelta

app = Flask(__name__)

# Gebruik /tmp voor Render.com (werkt altijd)
# OF gebruik in-memory als bestanden niet werken
USE_MEMORY = True  # Zet op False als je wel bestanden wilt proberen

# In-memory storage (werkt altijd)
memory_db = {}

def get_db():
    if USE_MEMORY:
        return memory_db
    # Anders probeer bestand
    DB_FILE = "/tmp/keys.json"
    if os.path.exists(DB_FILE):
        with open(DB_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_db(data):
    if USE_MEMORY:
        global memory_db
        memory_db = data
        return
    # Anders sla op in bestand
    DB_FILE = "/tmp/keys.json"
    try:
        with open(DB_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    except:
        pass  # Als het niet lukt, gebruik alleen memory

def create_key_folder(key, name, key_type):
    """Maakt key info (alleen in memory op Render)"""
    if key_type == "1m":
        expires = datetime.now() + timedelta(days=30)
    elif key_type == "3m":
        expires = datetime.now() + timedelta(days=90)
    else:  # lifetime
        expires = "never"
    
    # Sla alleen op in database, geen mapjes op Render (geen permanente opslag)
    return expires

@app.route('/')
def home():
    return "Auth Server Running! Keys in memory: " + str(len(get_db()))

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
        expires = create_key_folder(key, name, key_type)
        
        # Sla op in database
        keys = get_db()
        keys[key] = {
            "name": name,
            "type": key_type,
            "expires": str(expires),
            "created": str(datetime.now()),
            "active": True,
            "uses": 0
        }
        save_db(keys)
        
        return jsonify({
            "success": True,
            "key": key,
            "type": key_type,
            "expires": str(expires)
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
        
        keys = get_db()
        
        if key in keys and keys[key].get("active", False):
            expires = keys[key]["expires"]
            
            # Check lifetime
            if expires == "never":
                keys[key]["uses"] = keys[key].get("uses", 0) + 1
                save_db(keys)
                return jsonify({
                    "valid": True, 
                    "expires": "Lifetime", 
                    "name": keys[key]["name"]
                })
            
            # Check vervaldatum
            try:
                expire_date = datetime.fromisoformat(expires)
                if datetime.now() < expire_date:
                    keys[key]["uses"] = keys[key].get("uses", 0) + 1
                    save_db(keys)
                    return jsonify({
                        "valid": True, 
                        "expires": expires, 
                        "name": keys[key]["name"]
                    })
                else:
                    return jsonify({"valid": False, "reason": "expired"})
            except:
                return jsonify({"valid": False, "reason": "date_error"})
        
        return jsonify({"valid": False, "reason": "not_found"})
        
    except Exception as e:
        return jsonify({"valid": False, "error": str(e)}), 500

# Admin: Lijst van alle keys
@app.route('/list')
def list_keys():
    return jsonify(get_db())

# Admin: Verwijder key
@app.route('/delete/<key>', methods=['DELETE'])
def delete_key(key):
    keys = get_db()
    if key in keys:
        del keys[key]
        save_db(keys)
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Key not found"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
