import pytest
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import app  # Ensure this correctly imports your Flask app

@pytest.fixture
def client():
    app.config['TESTING'] = True  # Enable testing mode
    with app.test_client() as client:  # Use the Flask test client
        with app.app_context():
            yield client  # Yield the test client to the tests
