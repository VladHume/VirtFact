from extensions import db

class Operation(db.Model):
    __tablename__ = 'operations'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(128), nullable=False)
    component_id = db.Column(db.Integer, nullable=False)
    product_type = db.Column(db.String(128), nullable=False)

    def __init__(self, name, component_id, product_type):
        self.name = name
        self.component_id = component_id
        self.product_type = product_type
