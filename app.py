from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import logging
from datetime import timedelta
import requests
import random
import time
import base64

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # For flashing messages
# VirusTotal API URL and API key
API_URL = 'https://www.virustotal.com/api/v3/urls'
API_KEY = '0e2137eaa2a2395599cf8a67f5ed8fe2503bf60d81085b412d4df15b6968e6df'

# Set up logging
logging.basicConfig(level=logging.DEBUG)

def get_db_connection():
    conn = sqlite3.connect('users.db')
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    if 'username' in session:
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        try:
            data = request.get_json()
            username = data['username']
            email = data['email']
            password = data['password']
            
            conn = get_db_connection()
            cursor = conn.cursor()

            cursor.execute('SELECT * FROM users WHERE username = ? OR email = ?', (username, email))
            existing_user = cursor.fetchone()
            
            if existing_user:
                if existing_user['username'] == username:
                    return jsonify({'message': 'Username already taken'}), 400
                if existing_user['email'] == email:
                    return jsonify({'message': 'Email already registered'}), 400

            password_hash = generate_password_hash(password)

            cursor.execute('INSERT INTO users (username, email, password) VALUES (?, ?, ?)', (username, email, password_hash))
            conn.commit()
            conn.close()
            
            return jsonify({'message': 'User registered successfully'})
        except Exception as e:
            logging.error('Error during registration: %s', e)
            return jsonify({'message': 'An error occurred during registration'}), 500

    return render_template('register.html')

@app.route('/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        username = data['username']
        password = data['password']
        remember_me = data.get('rememberMe', False)
        
        logging.debug('Login attempt for username: %s', username)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
        user = cursor.fetchone()
        conn.close()
        
        if user:
            logging.debug('User found in database: %s', user['username'])
            if check_password_hash(user['password'], password):
                logging.debug('Password check successful for username: %s', username)
                session['username'] = username
                session['email'] = user['email']
                if remember_me:
                    session.permanent = True
                    app.permanent_session_lifetime = timedelta(days=30)
                else:
                    session.permanent = False
                return jsonify({'message': 'Login successful'})
            else:
                logging.debug('Invalid password for username: %s', username)
                return jsonify({'message': 'Invalid password'}), 400
        else:
            logging.debug('Invalid username: %s', username)
            return jsonify({'message': 'Invalid username'}), 400
    except Exception as e:
        logging.error('Error during login: %s', e)
        return jsonify({'message': 'An error occurred during login'}), 500

@app.route('/dashboard')
def dashboard():
    if 'username' in session:
        return render_template('dashboard.html', username=session['username'], email=session['email'])
    else:
        return redirect(url_for('index'))

@app.route('/tools')
def tools_page():
    return render_template('tools.html')

@app.route('/profile')
def profile():
    if 'username' in session:
        return render_template('profile.html', username=session['username'], email=session['email'])
    else:
        return redirect(url_for('index'))

@app.route('/settings')
def settings():
    if 'username' in session:
        return render_template('settings.html', username=session['username'], email=session['email'])
    else:
        return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/detect_ip')
def detect_ip():
    try:
        if request.headers.get('X-Forwarded-For'):
            user_ip = request.headers.get('X-Forwarded-For').split(',')[0]
        else:
            user_ip = request.remote_addr

        response = requests.get(f'http://ipinfo.io/{user_ip}/json')
        data = response.json()
        
        return jsonify({
            'IP': data.get('ip'),
            'City': data.get('city'),
            'Region': data.get('region'),
            'Country': data.get('country'),
            'Timezone': data.get('timezone'),
            'ISP': data.get('org')  # 'org' usually contains the ISP name
        })
    except Exception as e:
        logging.error('Error fetching IP details: %s', e)
        return jsonify({'message': 'An error occurred while fetching IP details'}), 500

@app.route('/ip_detector')
def ip_detector():
    return render_template('detect_ip.html')

@app.route('/ip_tracker')
def ip_tracker():
    return render_template('ip_tracker.html')

@app.route('/track_ip', methods=['POST'])
def track_ip():
    ip = request.form.get('ip')
    url = f"http://ip-api.com/json/{ip}"
    
    try:
        response = requests.get(url)
        data = response.json()
        
        if data['status'] == 'fail':
            return jsonify({'error': data['message']})
        
        return jsonify({
            'IP': data['query'],
            'City': data['city'],
            'Region': data['regionName'],
            'Country': data['country'],
            'Country Code': data['countryCode'],
            'Timezone': data['timezone'],
            'ISP': data['isp'],
            'Org': data['org'],
            'AS': data['as'],
            'Lat': data['lat'],
            'Lon': data['lon']
        })
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/url_scanner')
def url_scanner():
    return render_template('url_scanner.html')

@app.route('/scan', methods=['POST'])
def scan():
    try:
        data = request.get_json()
        url = data.get('url')
        result = check_url_safety(url)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)})

def check_url_safety(url):
    headers = {
        'x-apikey': API_KEY,
    }

    # Encode URL for the API request
    encoded_url = base64.urlsafe_b64encode(url.encode()).decode().strip("=")
    full_url = f'{API_URL}/{encoded_url}'

    try:
        response = requests.get(full_url, headers=headers)
        response.raise_for_status()
        status = response.json()
        print(f"API Response: {status}")  # Debug: Print API response

        # Adjust according to actual API response
        if 'data' in status and 'attributes' in status['data']:
            last_analysis_stats = status['data']['attributes']['last_analysis_stats']
            if last_analysis_stats['malicious'] > 0:
                return {'safe': False}
            else:
                return {'safe': True}
        else:
            return {'safe': False}
    except requests.RequestException as e:
        print(f"Error: {e}")  # Debug: Print the exception
        return {'error': str(e)}

@app.route('/hackmap')
def hackmap():
    return render_template('hackmap.html')

@app.route('/get-attack-data', methods=['GET'])
def get_attack_data():
    # Simulate the number of attacks and data over time
    current_time = time.strftime('%H:%M:%S')
    attacks_today = random.randint(100, 150)
    attack_data = {
        'attack_count': attacks_today,
        'graph_data': {
            'time': current_time,
            'attacks': random.randint(1, 10)
        },
        'locations': [
            {'lat': random.uniform(-90, 90), 'lng': random.uniform(-180, 180), 'time': current_time, 'severity': random.choice(['Low', 'Medium', 'High'])}
            for _ in range(random.randint(1, 5))
        ]
    }
    return jsonify(attack_data)

if __name__ == '__main__':
    app.run(debug=True)
