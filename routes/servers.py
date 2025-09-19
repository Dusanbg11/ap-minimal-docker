from flask import Blueprint, render_template, request, redirect, session, url_for, flash, Response
from extensions import mysql
from routes.logger import log_action
from io import StringIO
import csv

servers_bp = Blueprint('servers_bp', __name__, url_prefix='/servers')


@servers_bp.route('/')
def servers():
    if 'user_id' not in session:
        return redirect('/')

    search_query = request.args.get('search', '', type=str)
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)

    cur = mysql.connection.cursor()

    if search_query:
        count_query = "SELECT COUNT(*) FROM servers WHERE name LIKE %s"
        cur.execute(count_query, ('%' + search_query + '%',))
        total_servers = cur.fetchone()[0]

        query = """
            SELECT * FROM servers
            WHERE name LIKE %s
            ORDER BY name
            LIMIT %s OFFSET %s
        """
        cur.execute(query, ('%' + search_query + '%', per_page, (page - 1) * per_page))
    else:
        count_query = "SELECT COUNT(*) FROM servers"
        cur.execute(count_query)
        total_servers = cur.fetchone()[0]

        query = """
            SELECT * FROM servers
            ORDER BY name
            LIMIT %s OFFSET %s
        """
        cur.execute(query, (per_page, (page - 1) * per_page))

    servers = cur.fetchall()
    cur.close()

    total_pages = (total_servers + per_page - 1) // per_page

    return render_template(
        'servers.html',
        servers=servers,
        search_query=search_query,
        page=page,
        total_pages=total_pages,
        per_page=per_page,
        total_entries=total_servers,
        export_url=url_for('servers_bp.export_servers_csv')
    )


@servers_bp.route('/add', methods=['POST'])
def add_server():
    if 'user_id' not in session:
        return redirect('/')

    name = request.form['name'].strip()
    ip = request.form['ip_address'].strip()
    description = request.form['description'].strip()

    cur = mysql.connection.cursor()

    # ✅ Provera da li već postoji server sa istim imenom ili IP adresom
    cur.execute("SELECT COUNT(*) FROM servers WHERE name = %s OR ip_address = %s", (name, ip))
    exists = cur.fetchone()[0]

    if exists:
        cur.close()
        flash('Server already exists.', 'danger')
        return redirect(url_for('servers_bp.servers'))

    # ✅ Ako ne postoji, nastavljamo sa dodavanjem
    cur.execute(
        "INSERT INTO servers (name, ip_address, description) VALUES (%s, %s, %s)",
        (name, ip, description)
    )
    mysql.connection.commit()
    cur.close()

    # ✅ Logovanje
    details = f"Server {name} ({ip}) added."
    log_action(session['username'], 'add', 'server', name, details)

    flash(f'Server "{name}" is added.', 'success')
    return redirect(url_for('servers_bp.servers'))

@servers_bp.route('/delete/<int:server_id>', methods=['POST'])
def delete_server(server_id):
    if 'user_id' not in session:
        return redirect('/')

    cur = mysql.connection.cursor()
    cur.execute("SELECT name, ip_address FROM servers WHERE id = %s", (server_id,))
    result = cur.fetchone()
    server_name = result[0] if result else 'Nepoznat'
    ip_address = result[1] if result else '???'

    cur.execute("DELETE FROM servers WHERE id = %s", (server_id,))
    mysql.connection.commit()
    cur.close()

    # Logovanje
    details = f"Server {server_name} ({ip_address}) was deleted."
    log_action(session['username'], 'delete', 'server', server_name, details)

    flash(f'Server "{server_name}" je obrisan.', 'warning')
    return redirect(url_for('servers_bp.servers'))



@servers_bp.route('/edit/<int:server_id>', methods=['GET', 'POST'])
def edit_server(server_id):
    if 'user_id' not in session:
        return redirect('/')

    cur = mysql.connection.cursor()

    if request.method == 'POST':
        new_name = request.form['name']
        new_ip = request.form['ip_address']
        new_desc = request.form['description']

        cur.execute("SELECT name, ip_address, description FROM servers WHERE id = %s", (server_id,))
        old = cur.fetchone()

        if old:
            old_name, old_ip, old_desc = old
            changes = []

            if old_name != new_name:
                changes.append(f"Name: '{old_name}' → '{new_name}'")
            if old_ip != new_ip:
                changes.append(f"IP: '{old_ip}' → '{new_ip}'")
            if (old_desc or '') != (new_desc or ''):
                changes.append(f"Description: '{old_desc or ''}' → '{new_desc or ''}'")

            if changes:
                details = "; ".join(changes)
                log_action(session['username'], 'edit', 'server', new_name, details)

        cur.execute("""
            UPDATE servers SET name = %s, ip_address = %s, description = %s WHERE id = %s
        """, (new_name, new_ip, new_desc, server_id))
        mysql.connection.commit()
        cur.close()

        flash(f'Server "{new_name}" updated successfully.', 'success')
        return redirect(url_for('servers_bp.servers'))

    # GET request – render edit form
    cur.execute("SELECT * FROM servers WHERE id = %s", (server_id,))
    server = cur.fetchone()
    cur.close()

    if not server:
        return "Server not found", 404

    return render_template('edit_server.html', server=server)


@servers_bp.route('/view/<int:server_id>')
def view_server(server_id):
    if 'user_id' not in session:
        return redirect('/')

    cur = mysql.connection.cursor()

    # meta podaci o serveru
    cur.execute("SELECT * FROM servers WHERE id = %s", (server_id,))
    server = cur.fetchone()

    # linked users za ovaj server: koristimo sektor iz app_users (nekada 'role')
    cur.execute("""
        SELECT
            au.id,         -- 0
            au.full_name,  -- 1
            au.email,      -- 2
            au.note,       -- 3
            au.sector      -- 4  (ranije au.role)
        FROM app_users au
        JOIN user_server us ON au.id = us.user_id
        WHERE us.server_id = %s
    """, (server_id,))
    linked_users = cur.fetchall()

    # svi potencijalni korisnici za assign
    cur.execute("SELECT id, full_name FROM app_users ORDER BY full_name ASC")
    all_users = cur.fetchall()

    cur.close()

    return render_template('view_server.html', server=server, users=linked_users, all_users=all_users)

@servers_bp.route('/view/<int:server_id>/assign_user', methods=['POST'])
def assign_user_to_server(server_id):
    if 'user_id' not in session:
        return redirect('/')

    user_id = int(request.form.get('user_id'))

    if not user_id:
        flash("User not selected.", "danger")
        return redirect(url_for('servers_bp.view_server', server_id=server_id))

    try:
        cur = mysql.connection.cursor()

        # Provera da li već postoji veza user-server
        cur.execute("""
            SELECT 1 FROM user_server WHERE user_id = %s AND server_id = %s
        """, (user_id, server_id))
        exists = cur.fetchone()

        if exists:
            flash("User is already assigned to this server.", "warning")
        else:
            cur.execute("""
                INSERT INTO user_server (user_id, server_id) VALUES (%s, %s)
            """, (user_id, server_id))
            mysql.connection.commit()

            # Uzimanje imena korisnika i servera za log
            cur.execute("SELECT full_name FROM app_users WHERE id = %s", (user_id,))
            user_name = cur.fetchone()[0]

            cur.execute("SELECT name FROM servers WHERE id = %s", (server_id,))
            server_name = cur.fetchone()[0]

            details = f"User {user_name} is asigned to server {server_name}."
            log_action(session['username'], 'assign', 'user-server', server_name, details)

            flash("User assigned successfully.", "success")

        cur.close()
    except Exception as e:
        flash(f"An error occurred: {e}", "danger")

    return redirect(url_for('servers_bp.view_server', server_id=server_id))


@servers_bp.route('/view/<int:server_id>/remove_user/<int:user_id>', methods=['POST'])
def remove_user_from_server(server_id, user_id):
    if 'user_id' not in session:
        return redirect('/')

    try:
        cur = mysql.connection.cursor()

        # Uzimanje imena korisnika i servera za log pre brisanja
        cur.execute("SELECT full_name FROM app_users WHERE id = %s", (user_id,))
        user_name = cur.fetchone()[0]

        cur.execute("SELECT name FROM servers WHERE id = %s", (server_id,))
        server_name = cur.fetchone()[0]

        cur.execute("DELETE FROM user_server WHERE user_id = %s AND server_id = %s", (user_id, server_id))
        mysql.connection.commit()

        details = f"User {user_name} is removed from server {server_name}."
        log_action(session['username'], 'remove', 'user-server', server_name, details)

        cur.close()
        flash("User removed from server.", "success")
    except Exception as e:
        flash(f"An error occurred: {e}", "danger")

    return redirect(url_for('servers_bp.view_server', server_id=server_id))



@servers_bp.route('/export')
def export_servers_csv():
    if 'user_id' not in session:
        return redirect('/')

    cur = mysql.connection.cursor()
    cur.execute("SELECT name, ip_address, description FROM servers")
    servers = cur.fetchall()
    cur.close()

    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(['Server Name', 'IP Address', 'Description'])
    cw.writerows(servers)

    output = si.getvalue()
    return Response(
        output,
        mimetype='text/csv',
        headers={"Content-Disposition": "attachment;filename=all_servers.csv"}
    )


@servers_bp.route('/<int:server_id>/export_users')
def export_users_for_server(server_id):
    if 'user_id' not in session:
        return redirect('/')

    cur = mysql.connection.cursor()

    # Fetch users linked to this server
    cur.execute("""
        SELECT u.full_name, u.email, u.sector
        FROM app_users u
        JOIN user_server us ON u.id = us.user_id
        WHERE us.server_id = %s
    """, (server_id,))
    users = cur.fetchall()
    cur.close()

    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(['Full Name', 'Email', 'Sector'])
    for user in users:
        cw.writerow(user)

    output = si.getvalue()
    return Response(
        output,
        mimetype='text/csv',
        headers={"Content-Disposition": f"attachment; filename=server_{server_id}_users.csv"}
    )
