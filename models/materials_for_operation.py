from extensions import db


class MaterialO(db.Model):
    __tablename__ = 'materials_for_operation'

    id = db.Column(db.Integer, primary_key=True)
    material_id = db.Column(db.Integer, nullable=False)
    operation_id = db.Column(db.Integer, nullable=False)

    def __init__(self, material_id, operation_id):
        self.material_id = material_id
        self.operation_id = operation_id