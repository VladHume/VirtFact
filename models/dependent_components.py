from extensions import db


class dComponent(db.Model):
    __tablename__ = 'dependent_components'

    id = db.Column(db.Integer, primary_key=True)
    component_id = db.Column(db.Integer, nullable=False)
    product_type = db.Column(db.String(128), nullable=False)
    operation_id = db.Column(db.Integer, nullable=False)

    def __init__(self, component_id, product_type, operation_id):
        self.component_id = component_id
        self.product_type = product_type
        self.operation_id = operation_id