import uuid
from datetime import datetime, timedelta, timezone
from extensions import db

def get_token_expiry():
    # Token expires 15 minutes from creation (we can adjust as needed, e.g., hours=24)
    return datetime.now(timezone.utc) + timedelta(minutes=15)

class User(db.Model):
    """Core Authentication Table"""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    is_verified = db.Column(db.Boolean, default=False)
    verification_token = db.Column(db.String(64), unique=True, default=lambda: uuid.uuid4().hex)
    token_expiry = db.Column(db.DateTime, default=get_token_expiry)

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
    plaid_access_token = db.Column(db.String, nullable=True)
    plaid_item_id = db.Column(db.String, nullable=True)
