from flask import Flask, render_template, request, redirect, session, flash, url_for
from datetime import timedelta
from werkzeug.security import check_password_hash
from config import Config
from extensions import mysql  

# Init app
app = Flask(__name__)
app.config.from_object(Config)

# Init MySQL
mysql.init_app(app)

print(app.url_map)

@app.before_request
def make_session_permanent():
    session.permanent = True
    app.permanent_session_lifetime = timedelta(minutes=30)

#maintanance mode#
@app.before_request
def check_maintenance_mode():
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

def is_maintenance_mode():
    cur = mysql.connection.cursor()
    cur.execute("SELECT maintenance_mode FROM settings WHERE id = 1")
    result = cur.fetchone()
    cur.close()
    return result and result[0] == 1

# Registracija blueprintova
from routes.servers import servers_bp
from routes.users import users_bp
from routes.applications import applications_bp
from routes.settings import settings_bp
from routes.settings_admin import admin_bp

app.register_blueprint(servers_bp)
app.register_blueprint(users_bp)
app.register_blueprint(applications_bp)
app.register_blueprint(settings_bp)
app.register_blueprint(admin_bp)

#try:
#    app.register_blueprint(admin_bp)
#except Exception as e:
#    print(f"[!!] Greška pri registraciji admin_bp: {e}")

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



# Pokretanje aplikacije
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
