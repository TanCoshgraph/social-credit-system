from flask import (
    Flask as flask, 
    render_template,
    redirect,
    request,
    session,
    g
)
import os
import sys

import datetime

import logging
logging.basicConfig(level=logging.DEBUG)

app = flask(__name__, instance_relative_config=True)

from sqlalchemy.engine import Engine
from sqlalchemy import event
import sqlite3

@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

import db_alchemy
import sqlalchemy
db = db_alchemy.add_database_to_app(app)

# ensure the instance folder exists
try:
    os.makedirs(app.instance_path)
except OSError:
    pass

ADMIN_ID = 42
app.secret_key = "super_secret_key" 

def admin_exists():
    return get_admin() != None

def create_admin():
    if not admin_exists():
        admin = Person(id=ADMIN_ID, name='admin', score=0, passcode='super_safe', allowance=100)
        create_object(admin)

class Person(db.Model):
    id = db.mapped_column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    score = db.Column(db.Integer, nullable=False)
    passcode = db.Column(db.String(80), nullable=True)
    allowance = db.Column(db.Integer, nullable=False)
    sent_transfers = db.relationship('Transfer', foreign_keys='Transfer.person_from_id', backref='sender', lazy=True)
    received_transfers = db.relationship('Transfer', foreign_keys='Transfer.person_to_id', backref='recipient', lazy=True)

    def __repr__(self):
        return f'<Person {self.name}: {vars(self)}>'

    def calculate_score(self):
        self.score = sum(list(map(lambda transfer : transfer.amount, self.received_transfers)))
        return self.score

    def calculate_allowance(self):
        todays_transfers = list(filter(lambda transfer : transfer.created_at.date() == datetime.datetime.now().date(), self.sent_transfers))
        todays_total = sum(list(map(lambda transfer : transfer.amount, todays_transfers)))
        self.allowance = max(100 - todays_total, 0)
        return self.allowance

class Transfer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Integer, nullable=False)
    note = db.Column(db.String(80), nullable=True)
    person_from_id = db.mapped_column(db.Integer, db.ForeignKey('person.id'), nullable=False)
    person_to_id = db.mapped_column(db.Integer, db.ForeignKey('person.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.now, nullable=False)

    def __repr__(self):
        return f'<Transfer {self.id}: {vars(self)}>'

def create_object(db_model_object):
    try: 
        db.session.add(db_model_object)
        db.session.commit()
    except sqlite3.IntegrityError:
        db.session.rollback()
        raise Exception("Error creating object: sqlite Integrity Error")
    except:
        db.session.rollback()
        raise Exception("Something went wrong")

def find_person(id):
    return db.session.query(Person).where(Person.id == id).first()

def find_person_by_name(name):
    return db.session.query(Person).where(Person.name == name).first()

def get_admin():
    return find_person(42)

def get_people():
    query = sqlalchemy.select(Person).where(Person.id != ADMIN_ID)
    people = db.session.execute(query)
    return list(map(lambda person: person[0], people))

def extract_object(query_result):
    return list(map(lambda row: row[0], query_result))

def get_all_people_info():
    people = get_people()
    people_info = []
    for person in people:
        person.calculate_allowance()
        person.calculate_score()
        person_info = {
            'id': person.id,
            'name': person.name,
            'score': person.score,
            'passcode': person.passcode,
            'allowance': person.allowance
        }
        people_info.append(person_info)
    return people_info

@app.route("/")
def hello_world():
    return render_dashboard(status=None)

@app.route('/test_set_id')
def test_set_id():
    session['user_id'] = 2
    return redirect('/')

default_user_id = 0

def retrieve_messages(person_id):
    person = find_person(person_id)
    messages = [transfer for transfer in person.received_transfers]
    return messages if (messages != None and messages != []) else None

def render_dashboard(status, messages_component_status=None):
    # Header
    if 'user_id' in session:
        user_id = session['user_id']
    else:
        user_id = default_user_id

    current_user = find_person(user_id)
    if current_user == None:
        return redirect('/login')
    else:
        return render_dashboard_signed_in(current_user)
    

def render_dashboard_signed_in(user, status=None, messages_component_status=None):
    people = get_people()
    for person in people:
        person.calculate_score()
    people_info = get_all_people_info()

    scores = list(map(lambda person: [person.score, person], people))
    max_person = max(people, key=lambda person: person.score)
    max_score = max_person.score
    maxes = list(filter(lambda person: person.score == max_score, people))
    unique_max = len(maxes) == 1

    leader = max_person if unique_max else None

    # Messages
    messages = retrieve_messages(user.id)
    if messages == None:
        messages_component_status = "No messages. They should call you Lonely Mc No messages the 3rd :("

    return render_template('dashboard.html',
                            current_user=user,
                            rows=people,
                            status=status,
                            messages_component_status=messages_component_status,
                            messages=messages,
                            people=people_info,
                            leader=leader)

@app.route("/transfer_points", methods=['POST'])
def attempt_points_transfer():
    sender_id = int(request.form["sender_id"])
    sender = find_person(sender_id)

    # Verify that sender is current_user 
    if sender_id != user_id:
        return "Unauthorized"

    amount = int(request.form["points"]) if request.form["points"] else 0
    recipient_id = int(request.form["recipient_id"])
    error_message = ""
    if amount == 0:
        error_message = "Amount must be non-zero. Try again"
    elif sender_id == recipient_id:
        error_message = "Sending points to yourself? Sad. Minus 5 points for bringing down the vibe"
        transfer = Transfer(amount=-5, note="Bringing down the vibe", person_from_id=ADMIN_ID, person_to_id=sender_id)
        create_object(transfer)
    elif sender.calculate_allowance() - amount < 0:
        error_message = "You don't have anough allowance! Try again tomorrow"
    elif (sender_id == user_id) & (sender != None) & (find_person(user_id) != None):
        note = request.form["note"]
        transfer = Transfer(amount=amount, note=note, person_from_id=sender_id, person_to_id=recipient_id)
        create_object(transfer)
        return redirect('/')
    else:
        print("current_user:")
        print(find_person(user_id))
        error_message = "Something went wrong"
    # TODO: Store error message in session
    print(error_message)
    return redirect('/')


@app.route("/retrieve_messages", methods=['POST'])
def retrieve_messages_route():
    return retrieve_messages()

@app.route("/login", methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        name = request.form["name"]
        person = find_person_by_name(name)
        if person:
            session['user_id'] = person.id
            return redirect('/')
        else:
            return "User not found <br> <a href='/'>Go Back</a>", 404
    return render_template('login.html')

@app.route("/logout", methods=['POST'])
def logout():
    session.clear()
    return redirect('/login')
