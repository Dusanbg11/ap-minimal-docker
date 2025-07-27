from flask import Blueprint, render_template, request, redirect, session, flash, url_for, Response
from extensions import mysql
from io import StringIO
from routes.logger import log_action
import csv
import math

applications_bp = Blueprint('applications_bp', __name__, url_prefix='/applications')

@applications_bp.route('/')
def applications():
    if 'user_id' not in session:
        return redirect('/')

    search_query = request.args.get('search', '', type=str)
    per_page = request.args.get('per_page', 10, type=int)
    page = request.args.get('page', 1, type=int)

    cur = mysql.connection.cursor()

    if search_query:
        count_query = """
            SELECT COUNT(*)
            FROM applications
            WHERE name LIKE %s
        """
        cur.execute(count_query, ('%' + search_query + '%',))
        total = cur.fetchone()[0]

        query = """
            SELECT a.id, a.name, a.version, a.server_id, a.description, s.name
            FROM applications a
            LEFT JOIN servers s ON a.server_id = s.id
            WHERE a.name LIKE %s
            ORDER BY a.name
            LIMIT %s OFFSET %s
        """
        cur.execute(query, ('%' + search_query + '%', per_page, (page - 1) * per_page))
    else:
        cur.execute("SELECT COUNT(*) FROM applications")
        total = cur.fetchone()[0]

        query = """
            SELECT a.id, a.name, a.version, a.server_id, a.description, s.name
            FROM applications a
            LEFT JOIN servers s ON a.server_id = s.id
            ORDER BY a.name
            LIMIT %s OFFSET %s
        """
        cur.execute(query, (per_page, (page - 1) * per_page))

    applications = cur.fetchall()

    cur.execute("SELECT id, name FROM servers")
    servers = cur.fetchall()
    cur.close()

    total_pages = math.ceil(total / per_page)

    return render_template(
        'applications.html',
        applications=applications,
        servers=servers,
        search_query=search_query,
        per_page=per_page,
        page=page,
        total=total,
        total_pages=total_pages
    )

@applications_bp.route('/add', methods=['POST'])
def add_application():
    if 'user_id' not in session:
        return redirect('/')

    name = request.form['name'].strip()
    version = request.form['version'].strip()
    server_id = request.form['server_id']
    server_id = int(server_id) if server_id.isdigit() else None
    description = request.form['description'].strip()

    cur = mysql.connection.cursor()

    if server_id:
        cur.execute("SELECT COUNT(*) FROM applications WHERE name = %s AND server_id = %s", (name, server_id))
    else:
        cur.execute("SELECT COUNT(*) FROM applications WHERE name = %s AND server_id IS NULL", (name,))

    exists = cur.fetchone()[0]

    if exists:
        cur.close()
        flash('Application already exists.', 'danger')
        return redirect(url_for('applications_bp.applications'))

    cur.execute(
        "INSERT INTO applications (name, version, server_id, description) VALUES (%s, %s, %s, %s)",
        (name, version, server_id, description)
    )
    mysql.connection.commit()

    server_name = None
    if server_id:
        cur.execute("SELECT name FROM servers WHERE id = %s", (server_id,))
        server_row = cur.fetchone()
        server_name = server_row[0] if server_row else f"ID {server_id}"

    server_info = f" on server '{server_name}'" if server_name else ""
    details = f"Added version {version} with description '{description}'{server_info}"
    log_action(session['username'], 'add', 'application', name, details)

    cur.close()
    flash(f'Application "{name}" is added.', 'success')
    return redirect(url_for('applications_bp.applications'))

@applications_bp.route('/edit/<int:application_id>', methods=['GET', 'POST'])
def edit_application(application_id):
    if 'user_id' not in session:
        return redirect('/')

    cur = mysql.connection.cursor()

    if request.method == 'POST':
        new_name = request.form['name']
        new_version = request.form['version']
        new_desc = request.form['description']
        new_server_id = request.form['server_id'] or None

        cur.execute("SELECT name, version, description, server_id FROM applications WHERE id = %s", (application_id,))
        old = cur.fetchone()

        if old:
            old_name, old_version, old_desc, old_server_id = old
            changes = []

            if old_name != new_name:
                changes.append(f"Name ('{old_name}') → ('{new_name}')")
            if (old_version or '') != (new_version or ''):
                changes.append(f"Version ('{old_version or ''}') → ('{new_version or ''}')")
            if (old_desc or '') != (new_desc or ''):
                changes.append(f"Description ('{old_desc or ''}') → ('{new_desc or ''}')")
            if str(old_server_id or '') != str(new_server_id or ''):
                old_server_name = 'None'
                new_server_name = 'None'
                if old_server_id:
                    cur.execute("SELECT name FROM servers WHERE id = %s", (old_server_id,))
                    res = cur.fetchone()
                    old_server_name = res[0] if res else f"ID {old_server_id}"
                if new_server_id:
                    cur.execute("SELECT name FROM servers WHERE id = %s", (new_server_id,))
                    res = cur.fetchone()
                    new_server_name = res[0] if res else f"ID {new_server_id}"
                changes.append(f"Server ('{old_server_name}') → ('{new_server_name}')")

            if changes:
                details = "; ".join(changes)
                log_action(session['username'], 'edit', 'application', new_name, details)

        cur.execute("""
            UPDATE applications SET name = %s, version = %s, description = %s, server_id = %s
            WHERE id = %s
        """, (new_name, new_version, new_desc, new_server_id, application_id))
        mysql.connection.commit()
        cur.close()

        flash(f'Application "{new_name}" updated successfully.', 'success')
        return redirect(url_for('applications_bp.applications'))

    cur.execute("""
        SELECT a.id, a.name, a.version, a.description, a.server_id, s.name
        FROM applications a
        LEFT JOIN servers s ON a.server_id = s.id
        WHERE a.id = %s
    """, (application_id,))
    application = cur.fetchone()

    cur.execute("SELECT id, name FROM servers ORDER BY name")
    servers = cur.fetchall()

    cur.close()

    if not application:
        return "Application not found", 404

    return render_template('edit_application.html', application=application, servers=servers)

@applications_bp.route('/delete/<int:application_id>', methods=['POST'])
def delete_application(application_id):
    if 'user_id' not in session:
        return redirect('/')

    cur = mysql.connection.cursor()
    cur.execute("SELECT name FROM applications WHERE id = %s", (application_id,))
    result = cur.fetchone()
    app_name = result[0] if result else 'Unknown'

    cur.execute("DELETE FROM applications WHERE id = %s", (application_id,))
    mysql.connection.commit()

    log_action(session['username'], 'delete', 'application', app_name, f"Application '{app_name}' (ID {application_id}) was deleted.")

    cur.close()
    return redirect(url_for('applications_bp.applications'))

@applications_bp.route('/view/<int:application_id>')
def view_application(application_id):
    if 'user_id' not in session:
        return redirect('/')

    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT a.id, a.name, a.version, a.description, a.server_id, s.name
        FROM applications a
        LEFT JOIN servers s ON a.server_id = s.id
        WHERE a.id = %s
    """, (application_id,))
    application = cur.fetchone()

    cur.execute("""
        SELECT au.id, au.full_name, au.email, au.note, au.role
        FROM app_users au
        JOIN user_application ua ON au.id = ua.user_id
        WHERE ua.application_id = %s
    """, (application_id,))
    linked_users = cur.fetchall()

    cur.execute("SELECT id, full_name FROM app_users")
    all_users = cur.fetchall()
    cur.close()

    return render_template('view_application.html', application=application, users=linked_users, all_users=all_users)


@applications_bp.route('/export_all')
def export_all_applications_csv():
    if 'user_id' not in session:
        return redirect('/')

    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT a.name, a.version, COALESCE(s.name, 'No server assigned'), a.description
        FROM applications a
        LEFT JOIN servers s ON a.server_id = s.id
    """)
    apps = cur.fetchall()
    cur.close()

    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(['Name', 'Version', 'Server', 'Description'])

    for app in apps:
        row = [val if val is not None else '' for val in app]
        cw.writerow(row)

    output = si.getvalue()
    return Response(
        output,
        mimetype='text/csv',
        headers={"Content-Disposition": "attachment;filename=all_applications.csv"}
    )

@applications_bp.route('/export/<int:application_id>')
def export_application_csv(application_id):
    if 'user_id' not in session:
        return redirect('/')

    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT a.name, a.version, COALESCE(s.name, 'No server assinged') AS server_name, a.description
        FROM applications a
        LEFT JOIN servers s ON a.server_id = s.id
        WHERE a.id = %s
    """, (application_id,))
    app_data = cur.fetchone()
    cur.close()

    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(['Name', 'Version', 'Server', 'Description'])

    if app_data:
        row = [field if field is not None else '' for field in app_data]
        cw.writerow(row)

    output = si.getvalue()
    return Response(
        output,
        mimetype='text/csv',
        headers={"Content-Disposition": f"attachment;filename=application_{application_id}_details.csv"}
    )

@applications_bp.route('/<int:application_id>/assign_user', methods=['POST'])
def assign_user_to_application(application_id):
    if 'user_id' not in session:
        return redirect('/')

    user_id = request.form.get('user_id')

    if not user_id:
        flash("User not selected.", "danger")
        return redirect(url_for('applications_bp.view_application', application_id=application_id))

    try:
        cur = mysql.connection.cursor()

        cur.execute("""
            SELECT 1 FROM user_application WHERE user_id = %s AND application_id = %s
        """, (user_id, application_id))
        exists = cur.fetchone()

        if exists:
            flash("User is already assigned to this application.", "warning")
        else:
            cur.execute("""
                INSERT INTO user_application (user_id, application_id)
                VALUES (%s, %s)
            """, (user_id, application_id))
            mysql.connection.commit()

            cur.execute("SELECT name FROM applications WHERE id = %s", (application_id,))
            app_name_result = cur.fetchone()
            app_name = app_name_result[0] if app_name_result else f"AppID {application_id}"

            cur.execute("SELECT full_name FROM app_users WHERE id = %s", (user_id,))
            user_result = cur.fetchone()
            user_name = user_result[0] if user_result else f"UserID {user_id}"

            log_action(session['username'], 'assign', 'application', app_name, f"Assigned user '{user_name}'")
            flash("User assigned successfully.", "success")

        cur.close()
    except Exception as e:
        flash(f"An error occurred: {e}", "danger")

    return redirect(url_for('applications_bp.view_application', application_id=application_id))

@applications_bp.route('/<int:application_id>/remove_user/<int:user_id>', methods=['POST'])
def remove_user_from_application(application_id, user_id):
    if 'user_id' not in session:
        return redirect('/')

    try:
        cur = mysql.connection.cursor()

        cur.execute("DELETE FROM user_application WHERE user_id = %s AND application_id = %s", (user_id, application_id))
        mysql.connection.commit()

        cur.execute("SELECT name FROM applications WHERE id = %s", (application_id,))
        app_name_result = cur.fetchone()
        app_name = app_name_result[0] if app_name_result else f"AppID {application_id}"

        cur.execute("SELECT full_name FROM app_users WHERE id = %s", (user_id,))
        user_result = cur.fetchone()
        user_name = user_result[0] if user_result else f"UserID {user_id}"

        log_action(session['username'], 'remove', 'application', app_name, f"Removed user '{user_name}'")
        flash("User removed from application.", "success")

        cur.close()
    except Exception as e:
        flash(f"An error occurred: {e}", "danger")

    return redirect(url_for('applications_bp.view_application', application_id=application_id))

