from extensions import db
from werkzeug.security import generate_password_hash, check_password_hash

class Company(db.Model):
    __tablename__ = 'companies'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(128), unique=True, nullable=False)

    def __init__(self, name):
        self.name = name