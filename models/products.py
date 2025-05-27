from extensions import db

class Product(db.Model):
    __tablename__ = 'products'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), unique=True, nullable=False)
    company_id = db.Column(db.Integer, nullable=False)

    blocks = db.relationship('Block', backref='product', lazy=True, cascade='all, delete-orphan')

    def __init__(self, name, company_id):
        self.name = name
        self.company_id = company_id