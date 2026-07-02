from flask import Blueprint, render_template, request, redirect, session, flash, url_for, Response
from extensions import mysql
from io import StringIO
from routes.logger import log_action
import csv
import math

databases_bp = Blueprint('databases_bp', __name__, url_prefix='/databases')


@databases_bp.route('/')
def databases():
    if 'user_id' not in session:
        return redirect('/')

    search_query = request.args.get('search', '', type=str)
    per_page = request.args.get('per_page', 10, type=int)
    page = request.args.get('page', 1, type=int)

    cur = mysql.connection.cursor()

    if search_query:
        like = '%' + search_query + '%'

        cur.execute("""
            SELECT COUNT(*)
            FROM database_inventory
            WHERE name LIKE %s
               OR version LIKE %s
               OR server_ip LIKE %s
               OR description LIKE %s
        """, (like, like, like, like))
        total = cur.fetchone()[0]

        cur.execute("""
            SELECT id, name, version, server_ip, description
            FROM database_inventory
            WHERE name LIKE %s
               OR version LIKE %s
               OR server_ip LIKE %s
               OR description LIKE %s
            ORDER BY name
            LIMIT %s OFFSET %s
        """, (like, like, like, like, per_page, (page - 1) * per_page))
    else:
        cur.execute("SELECT COUNT(*) FROM database_inventory")
        total = cur.fetchone()[0]

        cur.execute("""
            SELECT id, name, version, server_ip, description
            FROM database_inventory
            ORDER BY name
            LIMIT %s OFFSET %s
        """, (per_page, (page - 1) * per_page))

    databases = cur.fetchall()
    cur.close()

    total_pages = math.ceil(total / per_page) if total else 1

    return render_template(
        'databases.html',
        databases=databases,
        search_query=search_query,
        per_page=per_page,
        page=page,
        total=total,
        total_pages=total_pages
    )


@databases_bp.route('/add', methods=['POST'])
def add_database():
    if 'user_id' not in session:
        return redirect('/')

    name = request.form['name'].strip()
    version = request.form.get('version', '').strip()
    server_ip = request.form.get('server_ip', '').strip()
    description = request.form.get('description', '').strip()

    cur = mysql.connection.cursor()

    cur.execute(
        "SELECT COUNT(*) FROM database_inventory WHERE name = %s AND server_ip = %s",
        (name, server_ip)
    )
    exists = cur.fetchone()[0]

    if exists:
        cur.close()
        flash('Database already exists.', 'danger')
        return redirect(url_for('databases_bp.databases'))

    cur.execute("""
        INSERT INTO database_inventory (name, version, server_ip, description)
        VALUES (%s, %s, %s, %s)
    """, (name, version, server_ip, description))

    mysql.connection.commit()

    log_action(
        session['username'],
        'add',
        'database',
        name,
        f"Added database version '{version}', IP '{server_ip}', description '{description}'"
    )

    cur.close()

    flash(f'Database "{name}" is added.', 'success')
    return redirect(url_for('databases_bp.databases'))


@databases_bp.route('/edit/<int:database_id>', methods=['GET', 'POST'])
def edit_database(database_id):
    if 'user_id' not in session:
        return redirect('/')

    cur = mysql.connection.cursor()

    if request.method == 'POST':
        new_name = request.form['name'].strip()
        new_version = request.form.get('version', '').strip()
        new_server_ip = request.form.get('server_ip', '').strip()
        new_desc = request.form.get('description', '').strip()

        cur.execute("""
            SELECT name, version, server_ip, description
            FROM database_inventory
            WHERE id = %s
        """, (database_id,))
        old = cur.fetchone()

        if old:
            old_name, old_version, old_server_ip, old_desc = old
            changes = []

            if old_name != new_name:
                changes.append(f"Name ('{old_name}') → ('{new_name}')")
            if (old_version or '') != (new_version or ''):
                changes.append(f"Version ('{old_version or ''}') → ('{new_version or ''}')")
            if (old_server_ip or '') != (new_server_ip or ''):
                changes.append(f"IP ('{old_server_ip or ''}') → ('{new_server_ip or ''}')")
            if (old_desc or '') != (new_desc or ''):
                changes.append(f"Description ('{old_desc or ''}') → ('{new_desc or ''}')")

            if changes:
                log_action(
                    session['username'],
                    'edit',
                    'database',
                    new_name,
                    "; ".join(changes)
                )

        cur.execute("""
            UPDATE database_inventory
            SET name = %s, version = %s, server_ip = %s, description = %s
            WHERE id = %s
        """, (new_name, new_version, new_server_ip, new_desc, database_id))

        mysql.connection.commit()
        cur.close()

        flash(f'Database "{new_name}" updated successfully.', 'success')
        return redirect(url_for('databases_bp.databases'))

    cur.execute("""
        SELECT id, name, version, server_ip, description
        FROM database_inventory
        WHERE id = %s
    """, (database_id,))
    database = cur.fetchone()

    cur.close()

    if not database:
        return "Database not found", 404

    return render_template('edit_database.html', database=database)


@databases_bp.route('/delete/<int:database_id>', methods=['POST'])
def delete_database(database_id):
    if 'user_id' not in session:
        return redirect('/')

    cur = mysql.connection.cursor()

    cur.execute("SELECT name FROM database_inventory WHERE id = %s", (database_id,))
    result = cur.fetchone()
    db_name = result[0] if result else 'Unknown'

    cur.execute("DELETE FROM database_inventory WHERE id = %s", (database_id,))
    mysql.connection.commit()

    log_action(
        session['username'],
        'delete',
        'database',
        db_name,
        f"Database '{db_name}' (ID {database_id}) was deleted."
    )

    cur.close()
    flash(f'Database "{db_name}" deleted.', 'success')
    return redirect(url_for('databases_bp.databases'))


@databases_bp.route('/view/<int:database_id>')
def view_database(database_id):
    if 'user_id' not in session:
        return redirect('/')

    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT id, name, version, server_ip, description
        FROM database_inventory
        WHERE id = %s
    """, (database_id,))
    database = cur.fetchone()

    if not database:
        cur.close()
        return "Database not found", 404

    cur.execute("""
        SELECT
            au.id,
            au.full_name,
            au.email,
            au.note,
            au.sector,
            ud.db_username,
            ud.db_grants
        FROM app_users au
        JOIN user_database ud ON au.id = ud.user_id
        WHERE ud.database_id = %s
        ORDER BY au.full_name ASC
    """, (database_id,))
    linked_users = cur.fetchall()

    cur.execute("SELECT id, full_name FROM app_users ORDER BY full_name ASC")
    all_users = cur.fetchall()

    cur.close()

    return render_template(
        'database_view.html',
        database=database,
        users=linked_users,
        all_users=all_users
    )


@databases_bp.route('/export_all')
def export_all_databases_csv():
    if 'user_id' not in session:
        return redirect('/')

    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT name, version, server_ip, description
        FROM database_inventory
        ORDER BY name ASC
    """)
    dbs = cur.fetchall()

    cur.close()

    si = StringIO()
    cw = csv.writer(si)

    cw.writerow(['Name', 'Version', 'IP Address', 'Description'])

    for db in dbs:
        cw.writerow([val if val is not None else '' for val in db])

    output = '\ufeff' + si.getvalue()

    return Response(
        output,
        mimetype='text/csv; charset=utf-8',
        headers={"Content-Disposition": "attachment;filename=all_databases.csv"}
    )


@databases_bp.route('/export/<int:database_id>')
def export_database_csv(database_id):
    if 'user_id' not in session:
        return redirect('/')

    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT name, version, server_ip, description
        FROM database_inventory
        WHERE id = %s
    """, (database_id,))
    db_data = cur.fetchone()

    cur.execute("""
        SELECT
            au.full_name,
            au.email,
            COALESCE(au.sector, '') AS sector,
            COALESCE(ud.db_username, '') AS db_username,
            COALESCE(ud.db_grants, '') AS db_grants,
            COALESCE(au.note, '') AS note
        FROM app_users au
        JOIN user_database ud ON ud.user_id = au.id
        WHERE ud.database_id = %s
        ORDER BY au.full_name ASC
    """, (database_id,))
    linked_users = cur.fetchall()

    cur.close()

    si = StringIO()
    cw = csv.writer(si)

    if db_data:
        cw.writerow(['Database Details'])
        cw.writerow(['Name', db_data[0] or ''])
        cw.writerow(['Version', db_data[1] or ''])
        cw.writerow(['IP Address', db_data[2] or ''])
        cw.writerow(['Description', db_data[3] or ''])
        cw.writerow([])

    cw.writerow(['Full Name', 'Email', 'Assignment', 'DB Username', 'Grants', 'Note'])

    for user in linked_users:
        cw.writerow([user[0], user[1], user[2], user[3], user[4], user[5]])

    output =  '\ufeff' + si.getvalue()
    filename = f"database_{database_id}_export.csv"

    return Response(
        output,
        mimetype='text/csv; charset=utf-8',
        headers={"Content-Disposition": f"attachment;filename={filename}"}
    )


@databases_bp.route('/<int:database_id>/assign_user', methods=['POST'])
def assign_user_to_database(database_id):
    if 'user_id' not in session:
        return redirect('/')

    user_id = request.form.get('user_id')
    db_username = (request.form.get('db_username') or '').strip()
    db_grants = (request.form.get('db_grants') or '').strip()

    if not user_id:
        flash("User not selected.", "danger")
        return redirect(url_for('databases_bp.view_database', database_id=database_id))

    if not db_username or not db_grants:
        flash("DB username and grants are required.", "danger")
        return redirect(url_for('databases_bp.view_database', database_id=database_id))

    try:
        cur = mysql.connection.cursor()

        cur.execute("SELECT name FROM database_inventory WHERE id = %s", (database_id,))
        db_row = cur.fetchone()
        db_name = db_row[0] if db_row else f"DatabaseID {database_id}"

        cur.execute("SELECT full_name FROM app_users WHERE id = %s", (user_id,))
        user_row = cur.fetchone()
        user_name = user_row[0] if user_row else f"UserID {user_id}"

        cur.execute("""
            SELECT db_username, db_grants
            FROM user_database
            WHERE user_id = %s AND database_id = %s AND db_username = %s
        """, (user_id, database_id, db_username))
        existing = cur.fetchone()

        if existing:
            old_grants = existing[1] or ''

            if old_grants == db_grants:
                flash("User is already assigned with the same DB username and grants.", "info")
            else:
                cur.execute("""
                    UPDATE user_database
                    SET db_grants = %s
                    WHERE user_id = %s AND database_id = %s AND db_username = %s
                """, (db_grants, user_id, database_id, db_username))

                mysql.connection.commit()

                log_action(
                    session['username'],
                    'edit',
                    'database',
                    db_name,
                    f"Updated grants for user '{user_name}', DB username '{db_username}': '{old_grants}' → '{db_grants}'"
                )

                flash("Database grants updated for this user.", "success")
        else:
            cur.execute("""
                INSERT INTO user_database (user_id, database_id, db_username, db_grants)
                VALUES (%s, %s, %s, %s)
            """, (user_id, database_id, db_username, db_grants))

            mysql.connection.commit()

            log_action(
                session['username'],
                'assign',
                'database',
                db_name,
                f"Assigned user '{user_name}' with DB username '{db_username}' and grants '{db_grants}'"
            )

            flash("User assigned to database successfully.", "success")

        cur.close()

    except Exception as e:
        flash(f"An error occurred: {e}", "danger")

    return redirect(url_for('databases_bp.view_database', database_id=database_id))


@databases_bp.route('/<int:database_id>/remove_user/<int:user_id>/<path:db_username>', methods=['POST'])
def remove_user_from_database(database_id, user_id, db_username):
    if 'user_id' not in session:
        return redirect('/')

    try:
        cur = mysql.connection.cursor()

        cur.execute("""
            DELETE FROM user_database
            WHERE user_id = %s AND database_id = %s AND db_username = %s
        """, (user_id, database_id, db_username))

        mysql.connection.commit()

        cur.execute("SELECT name FROM database_inventory WHERE id = %s", (database_id,))
        db_name_result = cur.fetchone()
        db_name = db_name_result[0] if db_name_result else f"DatabaseID {database_id}"

        cur.execute("SELECT full_name FROM app_users WHERE id = %s", (user_id,))
        user_result = cur.fetchone()
        user_name = user_result[0] if user_result else f"UserID {user_id}"

        log_action(
            session['username'],
            'remove',
            'database',
            db_name,
            f"Removed user '{user_name}' with DB username '{db_username}'"
        )

        flash("User removed from database.", "success")

        cur.close()

    except Exception as e:
        flash(f"An error occurred: {e}", "danger")

    return redirect(url_for('databases_bp.view_database', database_id=database_id))
