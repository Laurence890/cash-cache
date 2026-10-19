from datetime import datetime, timezone
from extensions import db

class User(db.Model):
    """Core Authentication Table"""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    profile = db.relationship('UserProfile', backref='user', uselist=False, cascade="all, delete-orphan")


class UserProfile(db.Model):
    """Public/Application Data Table"""
    __tablename__ = 'user_profiles'

    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)
    username = db.Column(db.String(50), unique=True, nullable=False, index=True)
    avatar_url = db.Column(db.String(500), nullable=True)
