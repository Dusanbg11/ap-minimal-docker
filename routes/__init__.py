from .servers import servers_bp
from .settings import settings_bp
from .users import users_bp
from .applications import applications_bp

def register_routes(app):
    app.register_blueprint(servers_bp)
    app.register_blueprint(applications_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(settings_bp)
