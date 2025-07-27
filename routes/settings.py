from flask import Blueprint, render_template, request, redirect, session, flash, send_file, current_app, url_for
from werkzeug.security import generate_password_hash
from extensions import mysql
from routes.logger import log_action
import subprocess
import datetime
import os
from datetime import timedelta

settings_bp = Blueprint('settings_bp', __name__, url_prefix='/settings')


@settings_bp.route('/')
def settings():
    if 'user_id' not in session:
        return redirect('/')
    return render_template('settings.html')


@settings_bp.route('/accounts')
def accounts():
    if 'user_id' not in session:
        return redirect('/')
    if not session.get('is_admin'):
        return render_template('access_denied.html'), 403
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM users")
    users = cur.fetchall()
    cur.close()
    return render_template('accounts.html', users=users)

@settings_bp.route('/accounts/add', methods=['POST'])
def add_account():
    if 'user_id' not in session or not session.get('is_admin'):
        return render_template('access_denied.html'), 403

    username = request.form['username']
    password = request.form['password']
    is_admin = 1 if 'is_admin' in request.form else 0
    hashed_password = generate_password_hash(password)

    cur = mysql.connection.cursor()
    cur.execute("INSERT INTO users (username, password, is_admin) VALUES (%s, %s, %s)",
                (username, hashed_password, is_admin))
    mysql.connection.commit()
    cur.close()

    # Log action
    action = "add"
    target_type = "account"
    target_name = username
    details = f"User account '{username}' created (admin={bool(is_admin)})"
    log_action(session['username'], action, target_type, target_name, details)

    return redirect('/settings/accounts')

@settings_bp.route('/accounts/edit/<int:user_id>', methods=['GET', 'POST'])
def edit_account(user_id):
    if 'user_id' not in session:
        return redirect('/')
    if not session.get('is_admin'):
        return render_template('access_denied.html'), 403

    cur = mysql.connection.cursor()

    if request.method == 'POST':
        username = request.form['username']
        password = request.form.get('password')
        is_admin = 1 if 'is_admin' in request.form else 0

        if password:
            hashed_password = generate_password_hash(password)
            cur.execute("UPDATE users SET username=%s, password=%s, is_admin=%s WHERE id=%s",
                        (username, hashed_password, is_admin, user_id))

            details = f"Account '{username}' updated with new password and admin={bool(is_admin)}"
        else:
            cur.execute("UPDATE users SET username=%s, is_admin=%s WHERE id=%s",
                        (username, is_admin, user_id))

            details = f"Account '{username}' updated: admin={bool(is_admin)}"

        mysql.connection.commit()
        cur.close()

        # Log action
        log_action(session['username'], 'edit', 'account', username, details)

        flash("Account updated successfully.", "success")
        return redirect('/settings/accounts')

    else:
        cur.execute("SELECT id, username, password, is_admin FROM users WHERE id = %s", (user_id,))
        user = cur.fetchone()
        cur.close()

        if not user:
            flash("User not found.", "danger")
            return redirect('/settings/accounts')

        return render_template('edit_account.html', user=user)


@settings_bp.route('/accounts/delete/<int:user_id>', methods=['POST'])
def delete_account(user_id):
    if 'user_id' not in session:
        return redirect('/')
    if not session.get('is_admin'):
        return render_template('access_denied.html'), 403

    cur = mysql.connection.cursor()
    cur.execute("SELECT username FROM users WHERE id = %s", (user_id,))
    user_result = cur.fetchone()

    if not user_result:
        cur.close()
        flash("User not found.", "danger")
        return redirect('/settings/accounts')

    username = user_result[0]

    cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
    mysql.connection.commit()
    cur.close()

    # Log action (standard format)
    action = "delete"
    target_type = "account"
    target_name = username
    details = f"User account '{username}' deleted"
    log_action(session['username'], action, target_type, target_name, details)

    flash("Account deleted successfully.", "success")
    return redirect('/settings/accounts')

@settings_bp.route('/change_password', methods=['GET', 'POST'])
def change_password():
    if 'user_id' not in session:
        return redirect('/')
    if request.method == 'POST':
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        if not new_password or new_password != confirm_password:
            flash("Passwords do not match.", "danger")
            return redirect('/settings/change_password')
        hashed_password = generate_password_hash(new_password)
        cur = mysql.connection.cursor()
        cur.execute("UPDATE users SET password=%s WHERE id=%s", (hashed_password, session['user_id']))
        mysql.connection.commit()
        cur.close()
        log_action(session['user_id'], "Changed their own password")
        flash("Password changed successfully.", "success")
        return redirect('/settings')
    return render_template('change_password.html')

@settings_bp.route('/theme', methods=['GET', 'POST'])
def theme_settings():
    if 'user_id' not in session:
        return redirect('/')
    if request.method == 'POST':
        preferred_theme = request.form.get('theme')
        session['theme'] = preferred_theme
        flash("Theme updated!", "success")
        return redirect('/settings')
    return render_template('theme_settings.html')

@settings_bp.route('/import')
def csv_import():
    return render_template('csv_import.html')

# 💾 Database Backup
@settings_bp.route('/backup')
def backup_database():
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect('/')
    db_user = current_app.config['MYSQL_USER']
    db_password = current_app.config['MYSQL_PASSWORD']
    db_name = current_app.config['MYSQL_DB']
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"backup_{db_name}_{timestamp}.sql"
    filepath = os.path.join("/tmp", filename)
    try:
        command = [
            "mysqldump",
            f"-u{db_user}",
            f"-p{db_password}",
            db_name
        ]
        with open(filepath, "w") as f:
            subprocess.run(command, stdout=f, check=True)
        return send_file(filepath, as_attachment=True, mimetype='application/sql', download_name=filename)
    except Exception as e:
        flash(f"Error during backup: {e}", "danger")
        return redirect('/settings')
