from extensions import db
from werkzeug.security import generate_password_hash, check_password_hash

class Account(db.Model):
    __tablename__ = 'accounts'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    login = db.Column(db.String(64), unique=True, nullable=False)
    _password = db.Column('password', db.String(128), nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    company_id = db.Column(db.Integer, nullable=True)

    def __init__(self, login, password, is_admin=False, company_id=None):
        self.login = login
        self.password = password
        self.is_admin = is_admin
        self.company_id = company_id

    @property
    def password(self):
        raise AttributeError('Пароль нечитабельний')

    @password.setter
    def password(self, plaintext):
        self._password = generate_password_hash(plaintext)

    def check_password(self, plaintext):
        return check_password_hash(self._password, plaintext)

    def __repr__(self):
        return f'<Account {self.login}, Admin: {self.is_admin}>'
