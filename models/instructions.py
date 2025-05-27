from extensions import db

class Instruction(db.Model):
    __tablename__ = 'instructions'

    id = db.Column(db.Integer, primary_key=True)
    operation_id = db.Column(db.Integer, nullable=False)
    photo_path = db.Column(db.String(255))
    video_path = db.Column(db.String(255))
    text_path = db.Column(db.String(255))

    def __init__(self, operation_id, photo_path, video_path, text_path):
        self.operation_id = operation_id
        self.photo_path = photo_path
        self.video_path = video_path
        self.text_path = text_path
