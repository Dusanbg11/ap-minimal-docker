from flask import Blueprint, render_template

help_bp = Blueprint('help_bp', __name__, url_prefix='/help')

@help_bp.route('/')
def help_page():
    return render_template('help.html')
