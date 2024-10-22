import pytest       
import io
from app import app  # Ensure this points to your Flask app

def test_signup(client):
    response = client.post('/signup', data={
        'email': 'test@example.com',
        'username': 'testuser',
        'password': 'password123'
    })
    assert response.status_code == 302  # Assuming a redirect after signup
    
def test_signup_existing_email(client):
    # First signup
    client.post('/signup', data={
        'email': 'test@example.com',
        'username': 'testuser',
        'password': 'password123'
    })
    
    # Try signing up again with the same email
    response = client.post('/signup', data={
        'email': 'test@example.com',
        'username': 'testuser2',
        'password': 'password1234'
    })
    assert b"Email is already taken" in response.data

def test_signup_empty(client):
    response = client.post('/signup', data={
        'email': '',
        'username': '',
        'password': ''
    })
    assert response.status_code == 200 #fail sign up
    assert b'All information fields are required.' in response.data




def test_signin(client):
    # First signup a user
    client.post('/signup', data={
        'email': 'test@example.com',
        'username': 'testuser',
        'password': 'password123'
    })

    # Then sign in
    response = client.post('/signin', data={
        'username': 'testuser',
        'password': 'password123'
    })
    assert response.status_code == 302  # Assuming a redirect after sign-in

def test_signin_invalid_password(client):
    # First signup a user
    client.post('/signup', data={
        'email': 'test@example.com',
        'username': 'testuser',
        'password': 'password123'
    })

    # Try signing in with the wrong password
    response = client.post('/signin', data={
        'username': 'testuser',
        'password': 'wrongpassword'
    })
    assert b"Password is invalid" in response.data

def test_signin_invalid_username(client):
    # First signup a user
    client.post('/signup', data={
        'email': 'test@example.com',
        'username': 'testuser',
        'password': 'password123'
    })

    # Try signing in with the wrong password
    response = client.post('/signin', data={
        'username': 'testuserwrong',
        'password': 'wrongpassword'
    })
    assert b"Username does not exist. Please sign up" in response.data

def test_signin_empty(client):
    # First signup a user
    client.post('/signup', data={
        'email': 'test@example.com',
        'username': 'testuser',
        'password': 'password123'
    })
    response = client.post('/signin',data={
        'username': '',
        'password': ''
    })
    assert response.status_code == 200  # Corrected to use status_code
    assert b"Username and password are required."in response.data

def test_fail_add_event(client):
    # Create a file-like object for the image
    image_data = io.BytesIO(b'file content here')  # Use actual image bytes if available
    image_data.filename = 'music.jpeg'
    
    response = client.post('/add-event', data={
        "name": 'Rock',
        "location": 'dd',
        "address": '3142dasd',
        "cost": '',  # Optional if paid is empty, but test empty input
        "category": 'music',
        "venue": 'georgia',
        "time": '2024-09-30T18:44',  # Use correct datetime-local format
        "capacity": '20',  # Capacity is required, test for empty input
        "image": image_data  # Pass the mock image file here
    })

    # Check that the response is a redirect (302) if the event is added successfully
    assert response.status_code == 302  # Assuming a redirect after successful event addition
  
def test_process_payment_failure(client):
    # Define the invalid payment data (missing card_number)
    invalid_payment_data = {
        "card_number": "",  # Missing card number
        "expiry_date": "12/25",
        "cvv": "123",
        "num_seats": "2",
        "total_cost": "100.00"
    }

    # Make a POST request to the payment processing route
    response = client.post('/process-payment', data=invalid_payment_data)

    # Check for a failure response (should render the payment page with an error)
    assert response.status_code == 200  # Should return to the same page
    assert b'Please enter all the require field' in response.data  # Adjust based on your error message