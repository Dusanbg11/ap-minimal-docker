from flask import Blueprint, render_template, session, redirect, flash, url_for, request, Response, jsonify
from extensions import mysql
from routes.logging import log_action
from werkzeug.security import check_password_hash
from datetime import datetime, timedelta
import csv
import io

admin_bp = Blueprint('admin', __name__, url_prefix='/settings/admin')

# ------------------------
# Helper Functions
# ------------------------
def verify_admin_password(password_input):
    cur = mysql.connection.cursor()
    cur.execute("SELECT password FROM users WHERE id = %s", (session['user_id'],))
    result = cur.fetchone()
    cur.close()
    return result and check_password_hash(result[0], password_input)

# ------------------------
# Admin Panel
# ------------------------

@admin_bp.route('/', endpoint='admin_panel')
def admin_panel():
    if 'user_id' not in session:
        return redirect('/')
    if not session.get('is_admin'):
        return render_template('access_denied.html'), 403
    return render_template('admin_panel.html')

# ------------------------
# Password Verification (JS only route)
# ------------------------
@admin_bp.route('/verify-password', methods=['POST'])
def verify_password():
    if 'user_id' not in session or not session.get('is_admin'):
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    
    password = request.form.get('password')
    return jsonify({"success": True}) if verify_admin_password(password) \
        else jsonify({"success": False, "message": "Incorrect password."})

# ------------------------
# Wipe Functions
# ------------------------
@admin_bp.route('/wipe/accounts', methods=['POST'], endpoint='wipe_accounts')
def wipe_accounts():
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect('/')

    password_input = request.form.get('password')
    if not verify_admin_password(password_input):
        flash("Incorrect password. Action not performed.", "danger")
        return redirect(url_for('admin.admin_panel'))

    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM users WHERE id != %s", (session['user_id'],))
    mysql.connection.commit()
    cur.close()
    flash("All login accounts (except yours) have been deleted.", "warning")
    return redirect(url_for('admin.admin_panel'))

@admin_bp.route('/wipe/app-users', methods=['POST'], endpoint='wipe_app_users')
def wipe_app_users():
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect('/')
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM app_users")
    mysql.connection.commit()
    cur.close()
    flash("All application users have been deleted.", "warning")
    return redirect(url_for('admin.admin_panel'))

@admin_bp.route('/wipe/servers', methods=['POST'], endpoint='wipe_servers')
def wipe_servers():
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect('/')
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM servers")
    mysql.connection.commit()
    cur.close()
    flash("All servers deleted.", "warning")
    return redirect(url_for('admin.admin_panel'))

@admin_bp.route('/wipe/apps', methods=['POST'], endpoint='wipe_apps')
def wipe_apps():
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect('/')
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM applications")
    mysql.connection.commit()
    cur.close()
    flash("All applications deleted.", "warning")
    return redirect(url_for('admin.admin_panel'))

@admin_bp.route('/wipe/all', methods=['POST'], endpoint='hard_reset')
def hard_reset():
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect('/')
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM app_users")
    cur.execute("DELETE FROM applications")
    cur.execute("DELETE FROM servers")
    cur.execute("DELETE FROM users WHERE id != %s", (session['user_id'],))
    mysql.connection.commit()
    cur.close()
    flash("Full reset completed. All data wiped except your account.", "danger")
    return redirect(url_for('admin.admin_panel'))

# ------------------------
# Audit Logs View and Wipe
# ------------------------
@admin_bp.route('/settings/audit-logs')
def view_logs():
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect('/')

    cur = mysql.connection.cursor()
    cur.execute("SELECT timestamp, actor, action, target_type, target_name, details FROM audit_logs ORDER BY timestamp DESC")
    rows = cur.fetchall()

    logs = [{
        'timestamp': row[0],
        'actor': row[1],
        'action': row[2],
        'target_type': row[3],
        'target_name': row[4],
        'details': row[5]
    } for row in rows]

    cur.execute("SELECT log_retention_days FROM settings LIMIT 1")
    result = cur.fetchone()
    cur.close()

    current_retention = int(result[0]) if result else 30
    return render_template('audit_logs.html', logs=logs, current_retention=current_retention)

@admin_bp.route('/wipe-logs', methods=['POST'])
def wipe_logs():
    if not verify_admin_password(request.form.get('password')):
        flash("Incorrect password.", "danger")
        return redirect(url_for('admin.view_logs'))

    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM audit_logs")
    mysql.connection.commit()
    cur.close()

    flash("Audit logs deleted.", "warning")
    return redirect(url_for('admin.view_logs'))

@admin_bp.route('/update_log_retention', methods=['POST'])
def update_log_retention():
    if 'user_id' not in session or not session.get('is_admin'):
        return render_template('access_denied.html'), 403
    try:
        days = int(request.form.get('log_days'))
        cur = mysql.connection.cursor()
        cur.execute("UPDATE settings SET log_retention_days = %s", (days,))
        mysql.connection.commit()
        cur.close()
        flash(f"Retention set to {days} days.", "success")
    except:
        flash("Failed to update retention setting.", "danger")
    return redirect(url_for('admin.view_logs'))

@admin_bp.route('/settings/audit-logs/export')
def export_logs():
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect('/')

    cur = mysql.connection.cursor()
    cur.execute("SELECT timestamp, actor, action, target_type, target_name, details FROM audit_logs ORDER BY timestamp DESC")
    logs = cur.fetchall()
    cur.close()

    output = io.StringIO()
    for row in logs:
        line = f"[{row[0]}] {row[1]} performed '{row[2]}' on {row[3]} '{row[4]}'"
        if row[5]:
            line += f" → {row[5]}"
        line += "\n"
        output.write(line)

    return Response(
        output.getvalue(),
        mimetype='text/plain',
        headers={"Content-Disposition": "attachment;filename=audit_logs.txt"}
    )

def delete_old_audit_logs():
    try:
        cur = mysql.connection.cursor()
        cur.execute("SELECT log_retention_days FROM settings LIMIT 1")
        result = cur.fetchone()
        cur.close()

        if result:
            retention_days = int(result[0])
            cutoff_date = datetime.now() - timedelta(days=retention_days)

            cur = mysql.connection.cursor()
            cur.execute("DELETE FROM audit_logs WHERE timestamp < %s", (cutoff_date,))
            deleted = cur.rowcount
            mysql.connection.commit()
            cur.close()

            if deleted > 0:
                print(f"[LOG CLEANUP] Deleted {deleted} old logs.")
    except Exception as e:
        print(f"[ERROR] Failed to delete old logs: {e}")

# ------------------------
# CSV Import/Export
# ------------------------
def handle_csv_import(table, required_fields, insert_sql):
    if 'user_id' not in session:
        return render_template('access_denied.html'), 403

    file = request.files.get('csv_file')
    if not file or file.filename == '' or not file.filename.endswith('.csv'):
        flash('Invalid CSV file.', 'danger')
        return redirect('/settings/import')

    try:
        decoded_file = io.TextIOWrapper(file.stream, encoding='utf-8-sig', errors='replace')
        reader = csv.DictReader(decoded_file)
        reader.fieldnames = [fn.lstrip('\ufeff') for fn in reader.fieldnames]

        if not set(required_fields).issubset(reader.fieldnames):
            flash(f'CSV must contain: {", ".join(required_fields)}.', 'danger')
            return redirect('/settings/import')

        imported = 0
        cur = mysql.connection.cursor()
        for row in reader:
            values = tuple(row[field].strip() for field in required_fields)
            cur.execute(insert_sql, values)
            imported += 1
        mysql.connection.commit()
        cur.close()

        flash(f'Successfully imported {imported} records into {table}.', 'success')
    except Exception as e:
        flash(f'Error importing CSV: {e}', 'danger')
    return redirect('/settings/import')

@admin_bp.route('/import-users-csv', methods=['POST'])
def import_users_csv():
    return handle_csv_import(
        table='app_users',
        required_fields=['full_name', 'email', 'note', 'role'],
        insert_sql="INSERT INTO app_users (full_name, email, note, role) VALUES (%s, %s, %s, %s)"
    )

@admin_bp.route('/import-servers-csv', methods=['POST'])
def import_servers_csv():
    return handle_csv_import(
        table='servers',
        required_fields=['name', 'ip_address', 'description'],
        insert_sql="INSERT INTO servers (name, ip_address, description) VALUES (%s, %s, %s)"
    )

@admin_bp.route('/import-applications-csv', methods=['POST'])
def import_applications_csv():
    return handle_csv_import(
        table='applications',
        required_fields=['name', 'version', 'description'],
        insert_sql="INSERT INTO applications (name, version, description) VALUES (%s, %s, %s)"
    )

# ------------------------
# CSV Templates
# ------------------------
def generate_csv_template(header, filename):
    return Response(
        header + "\n",
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename={filename}"}
    )

@admin_bp.route('/download-users-template')
def download_users_template():
    return generate_csv_template("name,email,note,role", "app_users_template.csv")

@admin_bp.route('/download-servers-template')
def download_servers_template():
    return generate_csv_template("name,ip_address,description", "servers_template.csv")

@admin_bp.route('/download-applications-template')
def download_applications_template():
    return generate_csv_template("name,version,description", "applications_template.csv")

