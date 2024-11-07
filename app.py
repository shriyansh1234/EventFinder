from flask import Flask, render_template, redirect, url_for, request, jsonify, flash
from events import events, save_events  # Import save_events function
from datetime import datetime, timedelta

import os
import mysql.connector
import pyodbc

app = Flask(__name__)
app.secret_key = 'ByteSize12'

print(pyodbc.drivers())

app.config['UPLOAD_FOLDER'] = 'static/images'

def connect_to_aws_rds():
    try:
        connection = pyodbc.connect(
            'DRIVER={MySQL ODBC 9.1 Unicode Driver};'  # Update the driver name if necessary
            'SERVER=the-horizon.c5u8ie6c0dqz.us-east-1.rds.amazonaws.com;'
            'DATABASE=ByteS;'
            'UID=ByteSize;'
            'PWD=SWEGroup12;'  # Replace with your actual password
            'PORT=3306;'  # MySQL default port
            'CHARSET=utf8;'  # Optional: specify character set
        )
        print("Connected to AWS RDS MySQL")
        return connection
    except pyodbc.Error as error:
        print("Error connecting to AWS RDS MySQL:", error)
        return None

# Query the database
def query_db(query, args=(), one=False):
    conn = connect_to_aws_rds()
    if conn is None:
        return None
    cursor = conn.cursor()
    cursor.execute(query, args)
    rows = cursor.fetchall()
    columns = [column[0] for column in cursor.description]

    def serialize_value(value):
        if isinstance(value, datetime):
            return value.isoformat()
        return value

    rv = [{columns[i]: serialize_value(value) for i, value in enumerate(row)} for row in rows]
    conn.close()
    return (rv[0] if rv else None) if one else rv

# Execute database commands
def execute_db(query, params=()):
    conn = connect_to_aws_rds()
    if conn is None:
        return None

    cursor = conn.cursor()
    try:
        if params and isinstance(params[0], tuple):
            cursor.executemany(query, params)
        else:
            cursor.execute(query, params)

        if query.strip().upper().startswith("SELECT"):
            results = cursor.fetchall()
            columns = [column[0] for column in cursor.description]
            return [dict(zip(columns, row)) for row in results]

        conn.commit()
        return None
    except pyodbc.Error as e:
        print(f"Database error: {e}")
        conn.rollback()
        return None
    finally:
        cursor.close()
        conn.close()

# POST endpoint to add a record
@app.route('/add_record', methods=['POST'])
def add_record():
    data = request.get_json()
    name = data.get('name')

    if not name:
        return jsonify({"error": "Name is required"}), 400

    query = "INSERT INTO ExampleTable (name) VALUES (?)"
    result = execute_db(query, (name,))

    if result is None:
        return jsonify({"message": "Record added successfully"}), 201
    else:
        return jsonify({"error": "Failed to add record"}), 500

# POST endpoint to get records
@app.route('/get_records', methods=['GET'])
def get_records():
    query = "SELECT * FROM Accounts"
    records = query_db(query)

    if records is not None:
        return jsonify(records), 200
    else:
        return jsonify({"error": "Failed to fetch records"}), 500



@app.route('/')
def index():
    return render_template('index.html')

#SIGN UP LOOP
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method =='POST':
        data = request.form
        email = data.get('email')
        password = data.get('password')

        if not email or not password:
            error_messege ="Email or pass word need to be fill out"
            return render_template("signup.html", error=error_messege)
        if user_exists(email):
            error_messege ="User is already exist!"
            return render_template("signup.html", error=error_messege)
        if add_user(email,password):
            return redirect(url_for('signin'))
        else:
            error_messege ="Sign up fail"
            return render_template("signup.html", error=error_messege)
    return render_template('signup.html')

#Check if user email exist
def user_exists(email):
    query = "SELECT * FROM Accounts WHERE email =?"
    user = query_db(query,(email,),one = True)
    return user is not None

#Add user if email credential not yet exist 
def add_user(email, password):
    connection = connect_to_aws_rds()  
    if connection is None:
        print("Connection to the database failed.")
        return False  
    
    try:
        cursor = connection.cursor()
        if user_exists(email):
            print(f"User with email {email} already exists.")
            return False 
        
        sql_insert_query = """INSERT INTO Accounts (email, user_pw, created_at) 
                              VALUES (?, ?, NOW())""" 
        cursor.execute(sql_insert_query, (email, password))
        
        connection.commit()
        
        print(f"User {email} added successfully!")
        return True
        
    except pyodbc.Error as error:
        print(f"Database error: {error}")
        return False
        
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return False
        
    finally:
        if connection is not None:
            cursor.close()
            connection.close()



#SIGN IN LOOP
@app.route('/signin', methods=['GET', 'POST'])
def signin():
    if request.method == 'POST':
        data = request.form
        email = data.get('email')
        password = data.get('password')
        if not email or not password:
            return jsonify({"error": "All fields are required"}),400
        if(user_and_password(email,password)):
            return redirect(url_for('main_app'))
        else:
            return render_template('signin.html', error="Invalid email or password")
    return render_template('signin.html')

#Check if email and password is correct 
def user_and_password(email,password):
    query = "SELECT * FROM Accounts WHERE email =? AND user_pw =?"
    user = query_db(query,(email,password),one=True)
    return user is not None




@app.route('/app')
def main_app():
    return render_template('/user/mainapp.html', events=events)

@app.route('/organizer')
def organizer():
    return render_template('/organizer/organizer.html')  # Create this template for the Organizer page


@app.route('/add-event', methods=['GET', 'POST'])
def add_event():
    if request.method == 'POST':
        # Gather form data
        event_name = request.form['name']
        description = request.form['description']
        category_id = request.form['category_id']
        location = request.form['location']
        date = request.form['date']
        event_time = request.form['event_time']
        capacity = int(request.form['capacity'])
        ticket_price = float(request.form['ticket_price']) if request.form.get('paid') == 'paid' else 0.0
        image_url = ""  # Placeholder for image URL if uploaded
        
        # Handle image upload
        if 'image_url' in request.files:
            image = request.files['image_url']
            if image.filename:
                image_filename = image.filename
                image.save(os.path.join(app.config['UPLOAD_FOLDER'], image_filename))
                image_url = image_filename
        
        # SQL query to insert the event
        query = """
            INSERT INTO Events (event_name, description, category_id, location, date, event_time, capacity, ticket_price, image_url, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NOW())
        """
        
        params = (event_name, description, category_id, location, date, event_time, capacity, ticket_price, image_url)
        
        # Execute query to insert event
        result = execute_db(query, params)
        
        if result is None:
            flash("Event added successfully!", "success")  # Feedback for successful addition
            return redirect(url_for('organizer'))
        else:
            flash("Failed to add the event. Please try again.", "error")  # Feedback for failure
            return render_template('/organizer/add_event.html')

    return render_template('/organizer/add_event.html')  # Render the add event form if GET request

@app.route('/event/<int:event_id>')
def event_details(event_id):
    if 0 <= event_id < len(events):
        event = events[event_id]  # Get the specific event based on its index
        return render_template('/user/event_details.html', event=event)
    return redirect(url_for('main_app'))  # Redirect if the event does not exist

@app.route('/filter', methods=['GET'])
def filter_events():
    distance = request.args.get('distance', type=float)
    max_cost = request.args.get('cost', type=float)
    event_type = request.args.get('eventType')
    category = request.args.get('category')


    # print(events)
    # print(category)
    # Apply filtering logic
    filtered_events = events

    if event_type == 'free':
        filtered_events = [event for event in filtered_events if not event['paid']]
    elif event_type == 'paid':
        filtered_events = [event for event in filtered_events if event['paid']]

    if category:
        # Convert both sides to lowercase for case-insensitive matching
        filtered_events = [event for event in filtered_events if event['category'].lower() == category.lower()]

    if max_cost is not None:
        filtered_events = [event for event in filtered_events if event['cost'] <= max_cost]

    return render_template('/user/mainapp.html', events=filtered_events)  # Render the filtered events



@app.route('/logout')
def logout():
    # Handle logout logic here (for now, we'll just redirect to the index page)
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)