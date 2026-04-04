def register_routes(app):
    from app.routes.shortener import shortener_bp
    from app.routes.users import users_bp
    app.register_blueprint(shortener_bp)

    from app.routes.url import url_bp
    app.register_blueprint(url_bp)
    app.register_blueprint(users_bp)
    
