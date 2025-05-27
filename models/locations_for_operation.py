from extensions import db


class LocationO(db.Model):
    __tablename__ = 'locations_for_operation'

    id = db.Column(db.Integer, primary_key=True)
    location_id = db.Column(db.Integer,  nullable=False)
    operation_id = db.Column(db.Integer,  nullable=False)

    def __init__(self, location_id, operation_id):
        self.location_id = location_id
        self.operation_id = operation_id