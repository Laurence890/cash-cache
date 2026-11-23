import uuid
from datetime import date, datetime, timedelta, timezone
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

class BudgetGoal(db.Model):
    """Custom Budget and Savings Goal linked to a specific user"""
    __tablename__ = 'budget_goals'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    target_amount = db.Column(db.Float, nullable=False)
    current_amount = db.Column(db.Float, default=0.0, nullable=False)
    # Time-frame
    start_date = db.Column(db.Date, default=date.today, nullable=False)
    target_date = db.Column(db.Date, nullable=False)
    # Status & auto-deletion tracking
    is_reached = db.Column(db.Boolean, default=False, nullable=False)
    reached_at = db.Column(db.Date, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    user = db.relationship('User', backref=db.backref('budget_goals', lazy=True, cascade="all, delete-orphan"))
    
    @property
    def total_days(self):
        delta = (self.target_date - self.start_date).days
        return max(1, delta)
    
    @property
    def total_months(self):
        """Calculates total months in the time-frame horizon."""
        months = (self.target_date.year - self.start_date.year) * 12 + (self.target_date.month - self.start_date.month)
        if months <= 0:
            months = max(1.0, round(self.total_days / 30.4375, 2))
        return float(months)
    
    @property
    def total_biweeks(self):
        """Calculates 14-day intervals across the time-frame horizon."""
        biweeks = self.total_days / 14.0
        return max(1.0, round(biweeks, 2))
    
    @property
    def monthly_savings_goal(self):
        """Breakdown of budget into monthly savings."""
        return round(self.target_amount / self.total_months, 2)
    
    @property
    def biweekly_savings_goal(self):
        """Breakdown of budget into bi-weekly (every 2 weeks) savings."""
        return round(self.target_amount / self.total_biweeks, 2)
    
    @property
    def percentage(self):
        if self.target_amount <= 0:
            return 0.0
        return min(100.0, round((self.current_amount / self.target_amount) * 100, 1))
    
    @property
    def remaining_amount(self):
        return max(0.0, round(self.target_amount - self.current_amount, 2))
    
    def update_progress(self, amount, today=None):
        """Updates saved progress and marks goal reached."""
        self.current_amount = max(0.0, float(amount))
        today = today or date.today()
        if self.current_amount >= self.target_amount:
            if not self.is_reached:
                self.is_reached = True
                self.reached_at = today
        else:
            self.is_reached = False
            self.reached_at = None
    
    def should_self_delete(self, current_date=None):
        """
        Self-deletes the following calendar month after being reached.
        Example: Reached in November 2026 -> deletes starting December 1, 2026.
        """
        if not self.is_reached or not self.reached_at:
            return False
        today = current_date or date.today()
        return (today.year > self.reached_at.year) or (
            today.year == self.reached_at.year and today.month > self.reached_at.month
        )

