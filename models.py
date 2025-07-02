from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password = db.Column(db.Text, nullable=False)
    name = db.Column(db.String(255))

class Team(db.Model):
    __tablename__ = 'teams'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), unique=True, nullable=False)
    logo_url = db.Column(db.String(512))

class Match(db.Model):
    __tablename__ = 'matches'
    id = db.Column(db.Integer, primary_key=True)
    team1_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=False)
    team2_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    team1 = db.relationship('Team', foreign_keys=[team1_id])
    team2 = db.relationship('Team', foreign_keys=[team2_id])

class Prediction(db.Model):
    __tablename__ = 'predictions'
    id = db.Column(db.Integer, primary_key=True)
    match_id = db.Column(db.Integer, db.ForeignKey('matches.id'), nullable=False)
    confidence = db.Column(db.Float, nullable=False)
    predicted_winner_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=False)
    data_points = db.Column(db.Text)  # JSON or stringified data points
    match = db.relationship('Match')
    predicted_winner = db.relationship('Team', foreign_keys=[predicted_winner_id])

class TopPrediction(db.Model):
    __tablename__ = 'top_predictions'
    id = db.Column(db.Integer, primary_key=True)
    prediction_id = db.Column(db.Integer, db.ForeignKey('predictions.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    prediction = db.relationship('Prediction')

class MatchResult(db.Model):
    __tablename__ = 'match_results'
    id = db.Column(db.Integer, primary_key=True)
    match_id = db.Column(db.Integer, db.ForeignKey('matches.id'), nullable=False)
    winner_id = db.Column(db.Integer, db.ForeignKey('teams.id'))
    score = db.Column(db.String(255))
    date = db.Column(db.Date, nullable=False)
    match = db.relationship('Match')
    winner = db.relationship('Team', foreign_keys=[winner_id])
