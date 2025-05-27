from extensions import db

class Block(db.Model):
    __tablename__ = 'blocks'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)

    details = db.relationship('Detail', backref='block', lazy=True, cascade='all, delete-orphan')

    def __init__(self, name, product_id):
        self.name = name
        self.product_id = product_id