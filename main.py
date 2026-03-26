"""
main.py — AuditGPT Application Entry Point (Person 3 — Final Integration)
Creates Flask app, registers blueprints, loads config.
"""

from flask import Flask
from dotenv import load_dotenv

load_dotenv()


def create_app():
    app = Flask(
        __name__,
        template_folder='ui/templates',
        static_folder='ui/static'
    )
    app.config['SECRET_KEY'] = 'auditgpt-dev-key'

    from ui.app import bp
    app.register_blueprint(bp)

    return app

# Expose the application globally for WSGI servers like Gunicorn
app = create_app()

if __name__ == '__main__':
    app.run(debug=True, port=5000)
