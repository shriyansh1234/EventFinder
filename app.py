from flask import Flask, render_template, redirect, url_for, request
import os
app = Flask(__name__)

# Your existing event data...
from events import events, save_events  # Import save_events function


app.config['UPLOAD_FOLDER'] = 'static/images'


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/signup')
def signup():
    return render_template('signup.html')

@app.route('/signin', methods=['GET', 'POST'])
def signin():
    if request.method == 'POST':
        return redirect(url_for('main_app'))
    return render_template('signin.html')

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
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
