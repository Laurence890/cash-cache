import unittest
from app import app, subscriptions_data


class TestSubscriptions(unittest.TestCase):

    def setUp(self):
        self.client = app.test_client()
        self.original_data = [item.copy() for item in subscriptions_data]

        with self.client.session_transaction() as session:
            session["logged_in"] = True

    def tearDown(self):
        subscriptions_data.clear()
        subscriptions_data.extend(self.original_data)

    def test_valid_subscription(self):
        original_count = len(subscriptions_data)
        original_total = sum(item["cost"] for item in subscriptions_data)

        response = self.client.post("/subscriptions", data={
            "name": "Disney+",
            "cost": "15.49",
            "billing_date": "2026-12-15"
        })

        new_total = sum(item["cost"] for item in subscriptions_data)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(subscriptions_data), original_count + 1)
        self.assertAlmostEqual(new_total, original_total + 15.49)

    def test_negative_cost(self):
        original_count = len(subscriptions_data)
        original_total = sum(item["cost"] for item in subscriptions_data)

        response = self.client.post("/subscriptions", data={
            "name": "Disney+",
            "cost": "-10",
            "billing_date": "2026-12-15"
        })

        new_total = sum(item["cost"] for item in subscriptions_data)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(subscriptions_data), original_count)
        self.assertAlmostEqual(new_total, original_total)

    def test_invalid_cost(self):
        original_count = len(subscriptions_data)

        response = self.client.post("/subscriptions", data={
            "name": "Disney+",
            "cost": "abc",
            "billing_date": "2026-12-15"
        })

        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(subscriptions_data), original_count)


if __name__ == "__main__":
    unittest.main()