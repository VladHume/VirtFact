from extensions import db

class Alarm(db.Model):
    __tablename__ = 'alarms'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    task_id = db.Column(db.Integer, nullable=False)
    text = db.Column(db.Text, nullable=False)

    def __init__(self, task_id, text):
        self.task_id = task_id
        self.text = text