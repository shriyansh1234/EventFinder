from flask import Flask, render_template, redirect, url_for, flash, request, jsonify, session
import os
import mysql.connector
app = Flask(__name__)
# Your existing event data...
#from events import events, save_events  # Import save_events function
from datetime import datetime, timedelta
import pyodbc

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


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
            session['email'] = email
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
        print("User Info: ", userinfo)
        if userinfo['user_exists']:
            session['user_id'] = userinfo['user']['user_id']  # Keeps track of user logged in
            session['email'] = userinfo['user']['email']
            session['first_name'] = userinfo['user']['first_name']
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


@app.route('/my_event')
def getEventsOrganizer():
    user_id = session.get('user_id')
    organizer_query = "SELECT organizer_id FROM Organizer WHERE user_id = ?"
    organizer = query_db(organizer_query, (user_id,), one=True)
    organizer_id = organizer['organizer_id']
    print(f"Organizer ID: {organizer_id}")

    query = """
            SELECT e.event_id, e.event_name, e.description, e.category_id, e.location, e.date, e.event_start,
       e.event_end, e.capacity, e.ticket_price, e.image_url, e.tickets_booked, e.created_at
FROM Events e
WHERE e.organizer_id = ?"""
    myEvent = query_db(query, organizer_id)
    print(myEvent)

    return render_template('organizer/my_event.html', myEvent=myEvent)

@app.route('/app')
def main_app():
    events=pull_data()
    return render_template('/user/mainapp.html', events=events)
def pull_data():
    user_id = session.get('user_id')
    query = """
        SELECT e.event_id, e.organizer_id, e.event_name, e.description, c.category_name, e.location, e.date, e.capacity, e.ticket_price, e.tickets_booked, e.created_at, e.image_url, e.paid, e.event_start
        FROM Events e
        JOIN Categories c ON e.category_id = c.category_id
        LEFT JOIN Interests i ON e.category_id = i.category_id AND i.user_id = ?
        ORDER BY i.user_id DESC, e.date ASC

    """
    events = query_db(query, (user_id))
    return events





@app.route('/organizer')
def organizer():
    return render_template('/organizer/organizer.html')  # Create this template for the Organizer page



@app.route('/add-event', methods=['GET', 'POST'])
def add_event():
    if request.method == 'POST':
        event_name = request.form['name']
        description = request.form['description']
        category_id = request.form['category_id']
        location = request.form['location']
        date = request.form['date']
        event_start = request.form['event_start']
        event_end = request.form['event_end']
        capacity = int(request.form['capacity'])
        paid = request.form['paid']  # Get the 'paid' value (free or paid)
        ticket_price = float(request.form['ticket_price']) if paid == 'paid' else 0.0
        image_url = ""  # Placeholder for image URL if uploaded

        # Handle image upload
        if 'image_url' in request.files:
            image = request.files['image_url']
            if image.filename:
                image_filename = image.filename
                image.save(os.path.join(app.config['UPLOAD_FOLDER'], image_filename))
                image_url = image_filename

        user_id = session.get('user_id')
        organizer_query = "SELECT organizer_id FROM Organizer WHERE user_id = ?"
        organizer = query_db(organizer_query, (user_id,), one=True)
        organizer_id = organizer['organizer_id']

        # Update parameters to include 'paid'
        params = (
            organizer_id, event_name, description, category_id, location,
            date, event_start, event_end, capacity, paid, ticket_price, image_url
        )

        query = """
            INSERT INTO Events (
                organizer_id, event_name, description, category_id, location,
                date, event_start, event_end, capacity, paid, ticket_price, image_url, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NOW())
        """

        result = execute_db(query, params)

        if result is None:
            flash("Event added successfully!", "success")
            return redirect(url_for('organizer'))
        else:
            flash("Failed to add the event. Please try again.", "error")
            return render_template('/organizer/add_event.html')

    return render_template('/organizer/add_event.html')







@app.route('/event/<int:event_id>',methods=['GET','POST'])
def event_details(event_id):
    query = """
        SELECT e.event_id, e.event_name, e.description, c.category_name, e.location, e.date, e.event_start, e.capacity, e.ticket_price, e.tickets_booked, e.image_url, e.paid
        FROM Events e
        JOIN Categories c ON e.category_id = c.category_id
        WHERE e.event_id = ?
    """

    event_details = query_db(query, (event_id,), one=True)
    print(event_details)
    if event_details is not None:
        # Event found, render details template
        print(event_details)
        return render_template('/user/event_details.html', event=event_details)
    else:
        # Event not found, handle error
        return redirect(url_for('main_app'))  # Or display an error message




""""
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
"""""
@app.route('/filter', methods=['GET'])
def filter_events():
    # Fetch filtering parameters
    distance = request.args.get('distance', type=float)
    max_cost = request.args.get('cost', type=float)
    event_type = request.args.get('eventType')
    category = request.args.get('category')
    start_date = request.args.get('startDate')
    end_date = request.args.get('endDate')
    print(category)
    # Base SQL query

    category_mapping = {
        'home-kitchen': 'Home & Kitchen',
        'health-beauty': 'Health & Beauty'
    }

    # If the category filter matches the key in the mapping, update it to the display name
    if category in category_mapping:
        category = category_mapping[category]


    query = """
        SELECT e.event_id, e.event_name, e.description, c.category_name, e.location, e.date, e.capacity, e.ticket_price, e.tickets_booked, e.image_url, e.paid, e.event_start
        FROM Events e
        JOIN Categories c ON e.category_id = c.category_id
        WHERE 1 = 1
    """
    params = []

    # Apply filters
    if category:
        query += " AND LOWER(c.category_name) = LOWER(?)"
        params.append(category)

    if max_cost is not None:
        query += " AND e.ticket_price <= ?"
        params.append(max_cost)

    if event_type:
        if event_type.lower() == 'free':
            query += " AND e.ticket_price = 0"
        elif event_type.lower() == 'paid':
            query += " AND e.ticket_price > 0"

    if start_date:
        query += " AND e.date >= ?"
        params.append(start_date)

    if end_date:
        query += " AND e.date <= ?"
        params.append(end_date)

    # Execute query
    events = query_db(query, params)
    if events is not None:
        return render_template('/user/mainapp.html', events=events)
    else:
        flash("No events match your filters.", "error")
        return redirect(url_for('main_app'))
    



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
            
            print(userid)
        
            organizer_info = get_organizer_info(userid)
            print("Hello", organizer_info)
            if organizer_info:
                session['is_organizer'] = True
                session['company_name'] = organizer_info['company_name']
                session['address'] = organizer_info['address']
                session['phone'] = organizer_info['phone']
            else:
                session['is_organizer'] = False

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



@app.route('/rsvp', methods=['POST'])
def bookEvent():
    userid = session.get('user_id')
    event = request.form.get('event_id')
    total = request.form.get('total_price')
    tickets = request.form.get('amount')
    booked = datetime.now()
    if userid is not None:
        connection = connect_to_aws_rds()
        if connection is None:
            return jsonify({"error": "Database connection failed"}), 500

        try:
            cursor = connection.cursor()
            query = """INSERT INTO Tickets (event_id, user_id, booking_date, ticket_amount, total_price)
                       VALUES(?, ?, ?, ?, ?)"""
            cursor.execute(query, (event, userid, booked, tickets, total))
            connection.commit()

            # Fetch user and event details to send email
            user_email = session.get('email')
            event_details = query_db(
                "SELECT event_name, date, location, ticket_price FROM Events WHERE event_id = ?", 
                (event,), one=True
            )



            if event_details:
                send_booking_confirmation_email(
                    to=user_email,
                    user_name=session.get('first_name', 'Guest'),
                    event_name=event_details['event_name'],
                    event_date=event_details['date'],
                    event_location=event_details['location'],
                    event_cost=event_details['ticket_price']
                )

            return redirect(url_for('confirm'))

        except pyodbc.Error as error:
            return jsonify({"error": "Database error"}), 500

        finally:
            cursor.close()
            connection.close()

    return jsonify({"error": "Not logged in"}), 400


@app.route('/confirmation')
def confirm():
    return render_template('confirmation.html')

@app.route('/bookings')
def getEvents():
    userid = session.get('user_id')
    query = """
            SELECT e.event_id, e.event_name, e.location, e.date, e.event_start, e.image_url, t.ticket_amount, t.total_price
            FROM Tickets t
            JOIN Events e ON t.event_id = e.event_id
            WHERE t.user_id = ?"""
    booked = query_db(query, userid)
    print(booked)
    return render_template('/user/bookings.html', booked=booked)

def send_booking_confirmation_email(to, user_name, event_name, event_date, event_location, event_cost):
    try:
        smtp_server = "smtp.gmail.com"
        smtp_port = 587
        smtp_user = "eventfinder.swe@gmail.com"  # Replace with your email
        smtp_password = "spiy xqut yeqt ntvm"     # Replace with your email password

        print("Starting email sending process...")
        print(f"Recipient: {to}")
        print(f"Event Details: {event_name}, {event_date}, {event_location}, {event_cost}")

        # Email content
        subject = "Booking Confirmation - Event Finder"

        text_body = f"""
        Hello {user_name},

        Thank you for RSVPing to the event "{event_name}"!

        Event Details:
        - Name: {event_name}
        - Date: {event_date}
        - Location: {event_location}
        - Cost: {"Free" if event_cost == 0 else f"${event_cost}"}

        You’ll receive this confirmation email as proof of your RSVP. Please have it ready when checking into the event.

        Stay safe and enjoy your time at the event!

        Best regards,
        Event Finder Team
        """
        print("Plain text body constructed.")

        html_body = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Booking Confirmation</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    margin: 0;
                    padding: 0;
                }}
                .container {{
                    width: 100%;
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 20px;
                    background-color: #f9f9f9;
                    border: 1px solid #ddd;
                    border-radius: 8px;
                }}
                .header {{
                    background-color: #28a745;
                    color: #ffffff;
                    padding: 10px 20px;
                    border-radius: 8px 8px 0 0;
                    text-align: center;
                }}
                .content {{
                    padding: 20px;
                }}
                .footer {{
                    text-align: center;
                    padding: 10px;
                    font-size: 0.9em;
                    color: #777;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Booking Confirmation</h1>
                </div>
                <div class="content">
                    <p>Hello {user_name},</p>
                    <p>Thank you for RSVPing to the event "<strong>{event_name}</strong>"!</p>
                    <p><strong>Event Details:</strong></p>
                    <ul>
                        <li><strong>Date:</strong> {event_date}</li>
                        <li><strong>Location:</strong> {event_location}</li>
                        <li><strong>Cost:</strong> {"Free" if event_cost == 0 else f"${event_cost}"}</li>
                    </ul>
                    <p>You’ll receive this confirmation email as proof of your RSVP. Please have it ready when checking into the event.</p>
                </div>
                <div class="footer">
                    <p>Event Finder Team</p>
                </div>
            </div>
        </body>
        </html>
        """
        print("HTML body constructed.")

        # Construct the email
        msg = MIMEMultipart('alternative')
        msg['From'] = smtp_user
        msg['To'] = to
        msg['Subject'] = subject

        msg.attach(MIMEText(text_body, 'plain'))
        msg.attach(MIMEText(html_body, 'html'))
        print("Email constructed with plain text and HTML parts.")

        # Send the email
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            print("Connecting to SMTP server...")
            server.starttls()
            print("Starting TLS encryption...")
            server.login(smtp_user, smtp_password)
            print("Logged in to SMTP server.")
            server.send_message(msg)
            print(f"Email sent successfully to {to}")

        return True

    except Exception as e:
        print("An error occurred during the email sending process.")
        print(f"Error: {e}")
        return False














if __name__ == '__main__':
    app.run(debug=True)


