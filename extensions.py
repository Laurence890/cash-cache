import os
from flask_sqlalchemy import SQLAlchemy
from argon2 import PasswordHasher
from passlib.context import CryptContext
import plaid
from plaid.api import plaid_api

db = SQLAlchemy()
ph = PasswordHasher()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Plaid Client Configuration
PLAID_CLIENT_ID = os.getenv("PLAID_CLIENT_ID", "your_test_client_id")
PLAID_SECRET = os.getenv("PLAID_SECRET", "your_test_secret")

configuration = plaid.Configuration(
    host=plaid.Environment.Sandbox,
    api_key={
        'clientId': PLAID_CLIENT_ID,
        'secret': PLAID_SECRET,
    }
)

api_client = plaid.ApiClient(configuration)
plaid_client = plaid_api.PlaidApi(api_client)