from flask_sqlalchemy import SQLAlchemy

def add_database_to_app(app):
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///second_db.sqlite'
    alchemy_db = SQLAlchemy(app)
    return alchemy_db