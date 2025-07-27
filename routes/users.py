from flask import Blueprint, render_template, request, redirect, session, Response, url_for, flash
from extensions import mysql
from io import StringIO
from routes.logger import log_action
import csv

users_bp = Blueprint('users_bp', __name__, url_prefix='/users')

# ------------------------
# View All Users (with search + pagination)
# ------------------------
@users_bp.route('/')
def users():
    if 'user_id' not in session:
        return redirect('/')

    search_query = request.args.get('search', '', type=str)
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)

    cur = mysql.connection.cursor()

    if search_query:
        count_query = "SELECT COUNT(*) FROM app_users WHERE full_name LIKE %s"
        cur.execute(count_query, ('%' + search_query + '%',))
        total_users = cur.fetchone()[0]

        query = """
            SELECT * FROM app_users
            WHERE full_name LIKE %s
            ORDER BY full_name
            LIMIT %s OFFSET %s
        """
        cur.execute(query, ('%' + search_query + '%', per_page, (page - 1) * per_page))
    else:
        count_query = "SELECT COUNT(*) FROM app_users"
        cur.execute(count_query)
        total_users = cur.fetchone()[0]

        query = """
            SELECT * FROM app_users
            ORDER BY full_name
            LIMIT %s OFFSET %s
        """
        cur.execute(query, (per_page, (page - 1) * per_page))

    app_users = cur.fetchall()
    cur.close()

    total_pages = (total_users + per_page - 1) // per_page

    return render_template(
        'users.html',
        app_users=app_users,
        search_query=search_query,
        page=page,
        total_pages=total_pages,
        per_page=per_page,
        total_entries=total_users,
        export_url=url_for('users_bp.export_all_users')
    )

# ------------------------
# View User Details
# ------------------------
@users_bp.route('/view/<int:user_id>')
def view_user(user_id):
    if 'user_id' not in session:
        return redirect('/')

    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM app_users WHERE id = %s", (user_id,))
    user = cur.fetchone()

    cur.execute("""
        SELECT s.id, s.name, s.ip_address, s.description
        FROM servers s
        JOIN user_server us ON s.id = us.server_id
        WHERE us.user_id = %s
    """, (user_id,))
    servers = cur.fetchall()

    cur.execute("""
        SELECT a.id, a.name, a.version, a.description
        FROM applications a
        JOIN user_application ua ON a.id = ua.application_id
        WHERE ua.user_id = %s
    """, (user_id,))
    applications = cur.fetchall()

    cur.close()
    return render_template('view_user.html', user=user, servers=servers, applications=applications)

# ------------------------
# Export User Links (Servers & Applications)
# ------------------------
@users_bp.route('/export/<int:user_id>')
def export_user_links(user_id):
    if 'user_id' not in session:
        return redirect('/')

    cur = mysql.connection.cursor()

    cur.execute("SELECT role FROM app_users WHERE id = %s", (user_id,))
    result = cur.fetchone()
    if not result:
        return "User not found", 404
    user_role = result[0]

    cur.execute("""
        SELECT s.name FROM servers s
        JOIN user_server us ON s.id = us.server_id
        WHERE us.user_id = %s
    """, (user_id,))
    servers = cur.fetchall()

    cur.execute("""
        SELECT a.name FROM applications a
        JOIN user_application ua ON a.id = ua.application_id
        WHERE ua.user_id = %s
    """, (user_id,))
    applications = cur.fetchall()

    cur.close()

    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(['Type', 'Name', 'Role'])
    for s in servers:
        cw.writerow(['Server', s[0], user_role])
    for a in applications:
        cw.writerow(['Application', a[0], user_role])

    output = si.getvalue()
    return Response(
        output,
        mimetype='text/csv',
        headers={"Content-Disposition": f"attachment;filename=user_{user_id}_access.csv"}
    )

# ------------------------
# Edit User
# ------------------------
@users_bp.route('/edit/<int:user_id>', methods=['GET', 'POST'])
def edit_user(user_id):
    if 'user_id' not in session:
        return redirect('/')

    cur = mysql.connection.cursor()

    if request.method == 'POST':
        new_full_name = request.form['full_name']
        new_email = request.form['email']
        new_note = request.form['note']
        new_role = request.form['role']

        # Get current values
        cur.execute("SELECT full_name, email, note, role FROM app_users WHERE id = %s", (user_id,))
        old = cur.fetchone()

        if old:
            old_full_name, old_email, old_note, old_role = old
            changes = []

            if old_full_name != new_full_name:
                changes.append(f"Full name: '{old_full_name}' → '{new_full_name}'")
            if old_email != new_email:
                changes.append(f"Email: '{old_email}' → '{new_email}'")
            if (old_note or '') != (new_note or ''):
                changes.append(f"Note: '{old_note or ''}' → '{new_note or ''}'")
            if old_role != new_role:
                changes.append(f"Role: '{old_role}' → '{new_role}'")

            if changes:
                details = "; ".join(changes)
                log_action(session['username'], 'edit', 'user', new_email, details)

        # Apply update
        cur.execute("""
            UPDATE app_users SET full_name = %s, email = %s, note = %s, role = %s WHERE id = %s
        """, (new_full_name, new_email, new_note, new_role, user_id))
        mysql.connection.commit()
        cur.close()
        flash(f'User "{new_full_name}" updated successfully.', 'success')
        return redirect(url_for('users_bp.users'))

    cur.execute("SELECT * FROM app_users WHERE id = %s", (user_id,))
    user = cur.fetchone()
    cur.close()

    if not user:
        return "User not found", 404

    return render_template('edit_user.html', user=user)

# ------------------------
# Add User
# ------------------------
@users_bp.route('/add', methods=['POST'])
def add_user():
    if 'user_id' not in session:
        return redirect('/')

    full_name = request.form['full_name']
    email = request.form['email']
    note = request.form['note']
    role = request.form['role']
    cur = mysql.connection.cursor()

    # Check for existing email
    cur.execute("SELECT id FROM app_users WHERE email = %s", (email,))
    existing_user = cur.fetchone()

    if existing_user:
        flash(f'User with email "{email}" already exists.', 'danger')
        cur.close()
        return redirect(url_for('users_bp.users'))

    # Insert new user
    cur.execute(
        "INSERT INTO app_users (full_name, email, note, role) VALUES (%s, %s, %s, %s)",
        (full_name, email, note, role)
    )
    mysql.connection.commit()

    # Log action
    details = f"User {full_name} is added"
    log_action(session['username'], 'add', 'user', full_name, details)

    flash(f'User "{full_name}" added successfully.', 'success')
    cur.close()
    return redirect(url_for('users_bp.users'))

# ------------------------
# Delete User
# ------------------------
@users_bp.route('/delete/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    if 'user_id' not in session:
        return redirect('/')

    cur = mysql.connection.cursor()

    # Fetch user details before deletion
    cur.execute("SELECT full_name, email, note FROM app_users WHERE id = %s", (user_id,))
    result = cur.fetchone()

    if result:
        full_name, email, note = result

        # Log the deletion
        details = f"User {full_name} is removed"
        log_action(session['username'], 'delete', 'user', full_name, details)

        # Delete the user
        cur.execute("DELETE FROM app_users WHERE id = %s", (user_id,))
        mysql.connection.commit()
        flash(f'User "{full_name}" deleted successfully.', 'success')
    else:
        flash("User not found.", 'danger')

    cur.close()
    return redirect(url_for('users_bp.users'))

# ------------------------
# Export All Users
# ------------------------
@users_bp.route('/export_all')
def export_all_users():
    if 'user_id' not in session:
        return redirect(url_for('users_bp.users'))

    cur = mysql.connection.cursor()
    cur.execute("SELECT id, full_name, email, note, role FROM app_users")
    users = cur.fetchall()
    cur.close()

    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(['ID', 'Full Name', 'Email', 'Note', 'Role'])

    for u in users:
        cw.writerow(u)

    output = si.getvalue()
    return Response(
        output,
        mimetype='text/csv',
        headers={"Content-Disposition": "attachment;filename=all_users.csv"}
    )

