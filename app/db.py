from flask_mysqldb import MySQL
from flask import current_app, g

def get_db():
    if 'db' not in g:
        g.db = MySQL.connect(
            current_app.config['DATABASE'],
            detect_types=MySQL.PARSE_DECLTYPES
        )
        g.db.row_factory = MySQL.Row

    return g.db


def close_db(e=None):
    db = g.pop('db', None)

    if db is not None:
        db.close()