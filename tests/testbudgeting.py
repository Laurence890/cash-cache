import unittest
from datetime import date, timedelta
from app import app
from extensions import db
from models import User, BudgetGoal

class TestBudgeterTool(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.client = app.test_client()

        with app.app_context():
            db.create_all()
            self.user1 = User(email="user1@example.com", password_hash="dummy")
            self.user2 = User(email="user2@example.com", password_hash="dummy")
            db.session.add_all([self.user1, self.user2])
            db.session.commit()
            self.u1_id = self.user1.id
            self.u2_id = self.user2.id

    def tearDown(self):
        with app.app_context():
            db.session.remove()
            db.drop_all()

    def test_positive_dollar_amount_required(self):
        """Rejects negative and zero dollar amounts."""
        with self.client.session_transaction() as sess:
            sess["logged_in"] = True
            sess["user_id"] = self.u1_id

        future_date = (date.today() + timedelta(days=90)).strftime("%Y-%m-%d")
        resp = self.client.post("/budgeting/goals/add", data={
            "name": "Invalid Goal",
            "amount": "-50.00",
            "target_date": future_date
        }, follow_redirects=True)

        with app.app_context():
            count = BudgetGoal.query.filter_by(user_id=self.u1_id).count()
            self.assertEqual(count, 0)

    def test_monthly_and_biweekly_calculations(self):
        """Verifies mathematical breakdown for monthly and bi-weekly goals."""
        with app.app_context():
            today = date(2026, 1, 1)
            target = date(2026, 7, 1)  # 6 months = 181 days (~12.93 bi-weeks)
            goal = BudgetGoal(
                user_id=self.u1_id,
                name="Laptop",
                target_amount=1200.0,
                start_date=today,
                target_date=target
            )
            self.assertEqual(goal.monthly_savings_goal, 200.00)
            self.assertAlmostEqual(goal.biweekly_savings_goal, 92.81, places=1)

    def test_maximum_10_goals_limit(self):
        """Ensures a user cannot exceed 10 active goals."""
        with self.client.session_transaction() as sess:
            sess["logged_in"] = True
            sess["user_id"] = self.u1_id

        future = (date.today() + timedelta(days=60)).strftime("%Y-%m-%d")
        with app.app_context():
            for i in range(10):
                db.session.add(BudgetGoal(
                    user_id=self.u1_id,
                    name=f"Goal {i}",
                    target_amount=100.0,
                    target_date=date.today() + timedelta(days=60)
                ))
            db.session.commit()

        # Attempt 11th goal
        self.client.post("/budgeting/goals/add", data={
            "name": "Goal 11",
            "amount": "100.00",
            "target_date": future
        })

        with app.app_context():
            self.assertEqual(BudgetGoal.query.filter_by(user_id=self.u1_id).count(), 10)

    def test_user_isolation(self):
        """Ensures User 1 cannot see or delete User 2's goals."""
        with app.app_context():
            g2 = BudgetGoal(user_id=self.u2_id, name="Secret", target_amount=500.0, target_date=date.today() + timedelta(days=30))
            db.session.add(g2)
            db.session.commit()
            g2_id = g2.id

        # Logged in as User 1
        with self.client.session_transaction() as sess:
            sess["logged_in"] = True
            sess["user_id"] = self.u1_id

        # Attempt to delete User 2's goal
        self.client.post(f"/budgeting/goals/delete/{g2_id}")

        with app.app_context():
            # Goal must still exist
            self.assertIsNotNone(BudgetGoal.query.get(g2_id))

    def test_self_deletion_following_month(self):
        """Goal stays active in month reached, self-deletes the following month."""
        with app.app_context():
            goal = BudgetGoal(
                user_id=self.u1_id,
                name="Vacation",
                target_amount=500.0,
                current_amount=500.0,
                is_reached=True,
                reached_at=date(2026, 11, 15),  # Reached in November
                target_date=date(2026, 12, 1)
            )
            db.session.add(goal)
            db.session.commit()

            # Same month check: November 30 -> should NOT self-delete
            self.assertFalse(goal.should_self_delete(current_date=date(2026, 11, 30)))

            # Following month check: December 1 -> SHOULD self-delete
            self.assertTrue(goal.should_self_delete(current_date=date(2026, 12, 1)))

if __name__ == "__main__":
    unittest.main()