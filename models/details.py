from extensions import db

class Detail(db.Model):
    __tablename__ = 'details'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    block_id = db.Column(db.Integer, db.ForeignKey('blocks.id'), nullable=False)

    def __init__(self, name, block_id):
        self.name = name
        self.block_id = block_id