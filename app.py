from flask import Flask, render_template, request, redirect, session, flash, url_for
from datetime import timedelta
from werkzeug.security import check_password_hash, generate_password_hash
from config import Config
from extensions import mysql
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Init app
app = Flask(__name__)
app.config.from_object(Config)

# Init MySQL
mysql.init_app(app)

# Globalna pre-request logika
@app.before_request
def global_before_request():
    session.permanent = True
    app.permanent_session_lifetime = timedelta(minutes=30)

    if request.endpoint in ['login', 'static']:
        return  # Dozvoli login i statičke fajlove

    if 'user_id' not in session:
        return  # Pusti neregistrovane da dođu do logina

    if session.get('is_admin'):
        return  # Admini mogu uvek

    cur = mysql.connection.cursor()
    cur.execute("SELECT maintenance_mode FROM settings WHERE id = 1")
    result = cur.fetchone()
    cur.close()

    if result and result[0] == 1:
        return render_template('maintenance.html'), 503

# Funkcija za proveru maintenance moda
def is_maintenance_mode():
    cur = mysql.connection.cursor()
    cur.execute("SELECT maintenance_mode FROM settings WHERE id = 1")
    result = cur.fetchone()
    cur.close()
    return result and result[0] == 1

# Registracija blueprintova
from routes.help import help_bp
from routes.servers import servers_bp
from routes.users import users_bp
from routes.applications import applications_bp
from routes.settings import settings_bp
from routes.settings_admin import admin_bp

app.register_blueprint(help_bp)
app.register_blueprint(servers_bp)
app.register_blueprint(users_bp)
app.register_blueprint(applications_bp)
app.register_blueprint(settings_bp)
app.register_blueprint(admin_bp)

# Login/logout i dashboard
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password_input = request.form['password']
        cur = mysql.connection.cursor()
        cur.execute("SELECT id, password, is_admin FROM users WHERE username = %s", (username,))
        user = cur.fetchone()
        cur.close()
        if user and check_password_hash(user[1], password_input):
            session['user_id'] = user[0]
            session['username'] = username
            session['is_admin'] = user[2]
            return redirect('/dashboard')
        else:
            flash('Incorrect username or password', 'danger')
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect('/')

    from routes.settings_admin import delete_old_audit_logs
    delete_old_audit_logs()

    return render_template('dashboard.html', username=session['username'])

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))

# Prvi put pokreni admin ako nema korisnika
with app.app_context():
    cur = mysql.connection.cursor()
    cur.execute("SHOW TABLES LIKE 'users'")
    if cur.fetchone():
        cur.execute("SELECT COUNT(*) FROM users WHERE username = %s", ("admin",))
        exists = cur.fetchone()[0]
        if exists == 0:
            username = os.environ.get("APP_ADMIN_USERNAME", "admin")
            password = os.environ.get("APP_ADMIN_PASSWORD", "admin")
            hashed_pw = generate_password_hash(password)
            cur.execute("INSERT INTO users (username, password, is_admin) VALUES (%s, %s, %s)",
                        (username, hashed_pw, True))
            mysql.connection.commit()
            print(f"[INFO] Admin account '{username}' is created.")
        else:
            print(f"[INFO] Admin account already exists.")
    cur.close()

# Pokretanje aplikacije
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
