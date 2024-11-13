from flask import Flask, render_template, redirect, url_for, request, jsonify, session
import os
import mysql.connector
app = Flask(__name__)
# Your existing event data...
from events import events, save_events  # Import save_events function
from datetime import datetime, timedelta
import pyodbc

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

app.secret_key = 'testing'

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
            error_messege ="Useralready exist!"
            return render_template("signup.html", error=error_messege)
        
        user_id = add_user(email, password)

        if(user_id):
            session['user_id'] = user_id
            return redirect(url_for('setname'))
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
        query = "SELECT user_id FROM Accounts WHERE email = ?"
        user_id = query_db(query, (email,), one=True)
        print(f"User {email} added successfully with user id:{user_id}!")
        return user_id['user_id']
        
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
            return jsonify({"error": "All fields are required"}), 400
        
        # Check if email and password are correct
        userinfo = user_and_password(email, password)
        print(userinfo)
        if userinfo['user_exists']:
            session['user_id'] = userinfo['user']['user_id']  # Keeps track of user logged in
            
            # Check if the user is an organizer and fetch additional details from the Organizer table
            user_id = userinfo['user']['user_id']
            organizer_info = get_organizer_info(user_id)
            print("Hello", organizer_info)
            if organizer_info:
                session['is_organizer'] = True
                session['company_name'] = organizer_info['company_name']
                session['address'] = organizer_info['address']
                session['phone'] = organizer_info['phone']
            else:
                session['is_organizer'] = False
            
            return redirect(url_for('main_app'))
        else:
            return render_template('signin.html', error="Invalid email or password")
    
    return render_template('signin.html')

def get_organizer_info(user_id):
    query = "SELECT company_name, address, phone FROM Organizer WHERE user_id = ?"
    organizer_info = query_db(query, (user_id,), one=True)
    return organizer_info


def user_and_password(email, password):
    query = "SELECT * FROM Accounts WHERE email =? AND user_pw =?"
    user = query_db(query, (email, password), one=True)
    
    # Check if user exists and return in the correct format
    return {'user_exists': user is not None, 'user': user}




@app.route('/app')
def main_app():
    return render_template('/user/mainapp.html', events=events)

@app.route('/organizer')
def organizer():
    return render_template('/organizer/organizer.html')  # Create this template for the Organizer page



@app.route('/add-event', methods=['GET', 'POST'])
def add_event():
    if request.method == 'POST':
        new_event = {
            "name": request.form['name'],
            "location": request.form['location'],
            "address": request.form['address'],
            "paid": request.form.get('paid') == 'on',
            "cost": float(request.form['cost']) if request.form.get('paid') == 'on' else 0,
            "category": request.form['category'],
            "venue": request.form['venue'],
            "time": request.form['time'],
            "capacity": int(request.form['capacity']),
            "image": ""  # Placeholder for the image file name
        }

        # Handle image upload
        if 'image' in request.files:
            image = request.files['image']
            if image.filename != '':
                image_filename = image.filename
                image.save(os.path.join(app.config['UPLOAD_FOLDER'], image_filename))
                new_event['image'] = image_filename
        
        events.append(new_event)  # Append new event to the events list
        save_events(events)  # Save updated events list to the JSON file
        return redirect(url_for('organizer'))  # Redirect to the organizer page after adding

    return render_template('/organizer/add_event.html')  # Render the add event form

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
    session.clear()
    return redirect(url_for('index'))


@app.route('/setname')
def setname():
    return render_template('setname.html')

@app.route('/submitName', methods=['POST'])
def submitname():
    Fname = request.form.get('firstname')
    Lname = request.form.get('lastname')
    is_organizer = request.form.get('organizer')  # "Yes" or "No"
    company_name = request.form.get('business_name') if is_organizer == "yes" else None
    address = request.form.get('business_address') if is_organizer == "yes" else None
    phone = request.form.get('business_phone') if is_organizer == "yes" else None
    
    userid = session.get('user_id')
    
    if userid is not None:
        connection = connect_to_aws_rds()  # Assumes connect_to_aws_rds() sets up your database connection
        
        if connection is None:
            print("Connection to the database failed.")
            return jsonify({"error": "Database connection failed"}), 500
        
        try:
            cursor = connection.cursor()
            
            # Update the user's name in the Accounts table
            query = "UPDATE Accounts SET first_name = ?, last_name = ? WHERE user_id = ?"
            cursor.execute(query, (Fname, Lname, userid))
            connection.commit()  # Commit the transaction
            
            # Update session with the new first name
            session['first_name'] = Fname
            print(f"User ID {userid} name updated successfully to {Fname} {Lname}")

            # If the user is an organizer, insert additional details into the Organizer table
            if is_organizer == "yes":
                # Update the Accounts table to mark the user as an organizer
                update_organizer_query = "UPDATE Accounts SET organizer = 1 WHERE user_id = ?"
                cursor.execute(update_organizer_query, (userid,))
                connection.commit()  # Commit the transaction
                print(f"User ID {userid} marked as an organizer in the Accounts table.")
                
                # Check if user already exists in the Organizer table
                check_query = "SELECT COUNT(*) FROM Organizer WHERE user_id = ?"
                cursor.execute(check_query, (userid,))
                count = cursor.fetchone()[0]
                
                if count == 0:
                    # Insert the organizer details into the Organizer table
                    insert_query = """
                        INSERT INTO Organizer (user_id, company_name, address, phone)
                        VALUES (?, ?, ?, ?)
                    """
                    cursor.execute(insert_query, (userid, company_name, address, phone))
                    connection.commit()  # Commit the transaction
                    print(f"User ID {userid} added to the Organizer table with company {company_name}")
                else:
                    print(f"User ID {userid} already exists in the Organizer table.")
            
            return redirect(url_for('interests'))

        except pyodbc.Error as error:
            print(f"Database error: {error}")
            return jsonify({"error": "Database update failed"}), 500

        finally:
            cursor.close()
            connection.close()
    
    else:
        return jsonify({"error": "Not logged in"}), 400


    

@app.route('/interests')
def interests():
    query = "SELECT * FROM Categories"
    categories = query_db(query)
    print(categories)
    return render_template('interests.html', categories=categories)

@app.route('/submitInterests', methods=['POST'])
def submitInterests():
    interests = request.form.getlist('interests')
    userid = session.get('user_id')
    if userid is not None:
            connection = connect_to_aws_rds()  # Assumes connect_to_aws_rds() sets up your database connection
            if connection is None:
                print("Connection to the database failed.")
                return jsonify({"error": "Database connection failed"}), 500
            
            try:
                cursor = connection.cursor()
                for interest in interests:
                    query = "INSERT INTO Interests (user_id, category_id) VALUES (?, ?)"
                    cursor.execute(query, (userid, interest))
                connection.commit()  # Commit the transaction
                
                print(f"User ID {userid} successfully submitted some interests~")
                return redirect(url_for('main_app')) 
                
            except pyodbc.Error as error:
                print(f"Database error: {error}")
                return jsonify({"error": "Database update failed"}), 500
            
            finally:
                cursor.close()
                connection.close()
        
    else:
        return jsonify({"error": "Not logged in"}), 400
    #return jsonify(interests)

if __name__ == '__main__':
    app.run(debug=True)
