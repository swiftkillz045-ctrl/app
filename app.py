from flask import Flask, request, jsonify
import uuid
import json
import os
from datetime import datetime, timedelta

app = Flask(__name__)

# Bestand waar keys worden opgeslagen (Render heeft permanente opslag)
DB_FILE = "/data/keys.json"

def load_keys():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_keys(keys):
    with open(DB_FILE, 'w') as f:
        json.dump(keys, f, indent=2)

def create_key_folder(key, name, key_type):
    """Maakt mapje aan met key bestand"""
    folder_path = f"/data/klanten/{name}_{key[:8]}"
    os.makedirs(folder_path, exist_ok=True)
    
    # Bepaal vervaldatum
    if key_type == "1m":
        expires = datetime.now() + timedelta(days=30)
    elif key_type == "3m":
        expires = datetime.now() + timedelta(days=90)
    else:  # lifetime
        expires = "never"
    
    # Sla key info op
    with open(f"{folder_path}/key_info.txt", 'w') as f:
        f.write(f"Naam: {name}\n")
        f.write(f"Key: {key}\n")
        f.write(f"Type: {key_type}\n")
        f.write(f"Geldig tot: {expires}\n")
        f.write(f"Aangemaakt: {datetime.now()}\n")
    
    return expires

@app.route('/')
def home():
    return "Auth Server Running!"

# Admin: Maak nieuwe key
@app.route('/create', methods=['POST'])
def create_key():
    data = request.json
    name = data.get("name")
    key_type = data.get("type", "1m")  # 1m, 3m, lifetime
    
    # Genereer unieke key (bijv: X7K9-M2P5-L8Q3-R4T6)
    key = '-'.join([uuid.uuid4().hex[:4].upper() for _ in range(4)])
    
    # Maakt mapje aan op server
    expires = create_key_folder(key, name, key_type)
    
    # Sla op in database
    keys = load_keys()
    keys[key] = {
        "name": name,
        "type": key_type,
        "expires": str(expires),
        "created": str(datetime.now()),
        "active": True,
        "uses": 0
    }
    save_keys(keys)
    
    return jsonify({
        "success": True,
        "key": key,
        "type": key_type,
        "expires": str(expires),
        "folder": f"klanten/{name}_{key[:8]}"
    })

# Client: Check of key geldig is
@app.route('/validate', methods=['POST'])
def validate_key():
    data = request.json
    key = data.get("key")
    
    keys = load_keys()
    
    if key in keys and keys[key]["active"]:
        expires = keys[key]["expires"]
        
        # Check lifetime
        if expires == "never":
            keys[key]["uses"] += 1
            save_keys(keys)
            return jsonify({"valid": True, "expires": "Lifetime", "name": keys[key]["name"]})
        
        # Check vervaldatum
        try:
            expire_date = datetime.fromisoformat(expires)
            if datetime.now() < expire_date:
                keys[key]["uses"] += 1
                save_keys(keys)
                return jsonify({"valid": True, "expires": expires, "name": keys[key]["name"]})
            else:
                return jsonify({"valid": False, "reason": "expired"})
        except:
            return jsonify({"valid": False})
    
    return jsonify({"valid": False, "reason": "not_found"})

# Admin: Lijst van alle keys
@app.route('/list')
def list_keys():
    keys = load_keys()
    return jsonify(keys)

# Admin: Verwijder key
@app.route('/delete/<key>', methods=['DELETE'])
def delete_key(key):
    keys = load_keys()
    if key in keys:
        del keys[key]
        save_keys(keys)
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Key not found"})

if __name__ == '__main__':
    # Maak data map aan als die niet bestaat
    os.makedirs("/data/klanten", exist_ok=True)
    app.run(host='0.0.0.0', port=10000)
