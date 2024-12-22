from flask import (
    Flask as flask, 
    render_template,
    redirect,
    request,
    session,
    g
)
import os
import db
import sys

import datetime

import logging
logging.basicConfig(level=logging.DEBUG)

import redis
cache = redis.Redis(host='redis-bobedis', port=6379)

app = flask(__name__, instance_relative_config=True)
app.config.from_mapping(
    DATABASE=os.path.join(app.instance_path, 'social-credit-system.sqlite'),
)
db.init_app(app)

# ensure the instance folder exists
try:
    os.makedirs(app.instance_path)
except OSError:
    pass

class Person:
    def __init__(self, name, score=0, _id=0, passcode=None, allowance=0,last_allowance_granted_date=None):
        self.id = _id
        self.name = name
        self.score = score
        self.passcode = passcode
        self.allowance = allowance
        self.last_allowance_granted_date = last_allowance_granted_date

    def calculate_score(self):
        transfers = get_received_transfers(self)
        self.score = sum(list(map(lambda transfer : transfer.amount, transfers)))
        return self.score

    def calculate_allowance(self):
        transfers = get_sent_transfers(self)
        todays_transfers = list(filter(lambda transfer : transfer.date == datetime.datetime.now().date(), transfers))
        todays_total = sum(list(map(lambda transfer : transfer.amount, todays_transfers)))
        self.allowance = max(100 - todays_total, 0)
        return self.allowance

class Transfer:
    def __init__(self, amount, note, sender_id, recipient_id):
        self.amount = amount

        if note != None:
            self.note = note
        else:
            sender = get_person_by_id(sender_id)
            self.note = f'{sender.name.capitalize()} didn\'t include a note. Kind of rude'
        self.sender_id = sender_id
        self.recipient_id = recipient_id

def create_person_table_db():
    drop_people = 'DROP TABLE IF EXISTS people'
    create_people = 'CREATE TABLE people(id INTEGER PRIMARY KEY NOT NULL, name TEXT NOT NULL, score INTEGER) WITHOUT ROWID'
    connection = db.get_db()
    connection.execute(drop_people)
    connection.execute(create_people)
    connection.commit()

def create_transfer_table_db():
    drop_transfers = 'DROP TABLE IF EXISTS transfers'
    create_transfers = 'CREATE TABLE transfers(id INTEGER PRIMARY KEY NOT NULL, amount INTEGER NOT NULL, note TEXT NOT NULL, person_from_id INTEGER NOT NULL, person_to_id INTEGER NOT NULL, FOREIGN_KEY(person_from_id) REFERENCES people(id), FOREIGN_KEY(person_to_id) REFERENCES people(id)) WITHOUT ROWID'
    connection = db.get_db()
    connection.execute(drop_transfers)
    connection.execute(create_transfers)
    connection.commit()

def create_person_db(person):
    connection = db.get_db()

    count = connection.execute('SELECT COUNT(id) FROM people').fetchone()[0]
    get_id = 'SELECT id FROM people ORDER BY id DESC LIMIT 1'
    
    new_id = 1 if count == 0 else connection.execute(get_id).fetchone()[0] + 1
    date = "NULL" if person.last_allowance_granted_date == None else typeify_item(person.last_allowance_granted_date)

    insert_row = f'INSERT INTO people (id, name, score, allowance, last_allowance_granted_date) VALUES ({new_id},"{person.name}",{person.score}, {person.allowance}, {date})'
    print(insert_row)
    connection.execute(insert_row)
    connection.commit()

def get_admin():
    get_person_by_id(42)

def create_transfer_db(transfer):
    connection = db.get_db()

    insert_row = '''insert into transfers (
                    amount, note, person_from_id, person_to_id)
                    values ({0}, "{1}", {2}, {3})'''.format(transfer.amount, transfer.note, transfer.sender_id, transfer.recipient_id)
    connection.execute(insert_row)
    connection.commit()

def row_to_person(sql_row):
    date_str = sql_row[5]
    date = None
    if date_str != None:
        date = datetime.datetime.strptime(date_str, "%y-%m-%d")
    person = Person(sql_row[1], sql_row[2], sql_row[0], sql_row[3], sql_row[4], date)
    person.calculate_score()
    person.calculate_allowance()
    return person

def row_to_transfer(sql_row):
    return Transfer(sql_row[1], sql_row[2], sql_row[3], sql_row[4])

def get_people():
    query = 'SELECT * FROM people where id != 42'
    connection = db.get_db()
    rows = connection.execute(query).fetchall()
    return list(map(row_to_person, rows))

def get_person_by_id(id):
    query = f'SELECT * FROM people WHERE id = {id}'
    connection = db.get_db()
    row = connection.execute(query).fetchone()
    return row_to_person(row)

# Format item for database
def typeify_item(v):
    val = None
    if isinstance(v, str):
        val = f'"{v}"'
    elif isinstance(v, datetime.datetime):
        val = v.strftime("%y-%m-%d")
    else:
        val = v
    return val

def update_person(id, attrs_dict):
    changes = ""
    for k,v in attrs_dict.items():
        val = typeify_item(v)
        changes += f'{k} = {val},'
    changes = changes[:-1]

    query = f'update people set {changes} where id = {id}'

    connection = db.get_db()
    connection.execute(query)
    connection.commit()

def get_sent_transfers(person):
    query = f'SELECT * FROM transfers where person_from_id = {person.id}'
    connection = db.get_db()
    rows = connection.execute(query).fetchall()
    return list(map(row_to_transfer, rows))

def get_received_transfers(person):
    query = f'SELECT * FROM transfers where person_to_id = {person.id}'
    connection = db.get_db()
    rows = connection.execute(query).fetchall()
    return list(map(row_to_transfer, rows))

def get_val_from_redis(id):
    retries = 5
    while True:
        try:
            val = cache.get(str(id))
            if val is None:
                return cache.set(str(id), 0)
            else:
                return int(val)
        except redis.exceptions.ConnectionError as exc:
            if retries == 0:
                raise exc
            retries -= 1
            time.sleep(0.5)

def increment_person_redis(id):
    try:
        return cache.incrby(str(id), 5)
    except redis.exceptions.ConnectionError as exc:
        raise exc

def decrement_person_redis(id):
    try:
        return cache.decrby(str(id), 5)
    except redis.exceptions.ConnectionError as exc:
        raise exc

def decrement_allowance(person, amount):
    if person.allowance <= 0:
        return
    update_person(person.id, { "allowance": person.allowance - abs(amount)})

def get_all_people_info():
    people = get_people()
    people_info = []
    for person in people:
        person_info = {
            'id': person.id,
            'name': person.name,
            'score': person.score,
            'passcode': person.passcode,
            'allowance': person.allowance,
            'last_allowance_granted_date': person.last_allowance_granted_date
        }
        people_info.append(person_info)
    return people_info

@app.route("/")
def hello_world():
    return render_dashboard(status=None)

def render_dashboard(status, messages_component_status=None, messages=None):
    people = get_people()
    for person in people:
        transfers = get_received_transfers(person)
        person.score = sum(list(map(lambda transfer : transfer.amount, transfers)))
    people_info = get_all_people_info()
    return render_template('scoreboard.html', rows=people, status=status, messages_component_status=messages_component_status, messages=messages, people=people_info)

@app.route("/increment", methods=['GET'])
def increment():
    people = get_people()
    id = request.args.get('id')
    increment_person_redis(id)
    return redirect('/')

@app.route("/decrement", methods=['GET'])
def decrement():
    people = get_people()
    id = request.args.get('id')
    decrement_person_redis(id)
    return redirect('/')

@app.route("/dashboard", methods=['GET'])
def login_page():
    return render_template('dashboard.html')

@app.route("/transfer_points", methods=['POST'])
def attempt_points_transfer():
    code = request.form["code"]
    print("Attempting transfer", file=sys.stdout, flush=True)
    print(f'code: {code}', file=sys.stdout, flush=True)
    sender_id = int(request.form["sender_id"])
    sender = get_person_by_id(int(sender_id))
    amount = int(request.form["points"])
    recipient_id = int(request.form["recipient_id"])
    error_message = ""
    if amount == 0:
        error_message = "Nice try"
    elif sender_id == recipient_id:
        error_message = "Sending points to yourself? Sad. Minus 5 points for bringing down the vibe"
        transfer = Transfer(-5, "Bringing down the vibe", 42, sender_id)
        create_transfer_db(transfer)
    elif sender.allowance - amount <= 0:
        error_message = "You don't have anough allowance!" 
    elif sender.passcode == None or code == sender.passcode:
        note = request.form["note"]
        transfer = Transfer(amount, note, sender_id, recipient_id)
        create_transfer_db(transfer)
        decrement_allowance(sender, transfer.amount)
        return redirect('/')
    else:
        error_message = "something went wrong (probably your passcode isn't right)"
    return render_template('scoreboard.html', status=error_message, rows=get_people(), people=get_all_people_info(), messages=None)

def retrieve_messages():
    passcode = request.form["passcode"]
    people = get_people()
    messages = []
    for person in people:
        if person.passcode == passcode:
            transfers = get_received_transfers(person)
            messages = [transfer.note for transfer in transfers if transfer.note]
            status = "They should call you Lonely Mc No messages the 3rd :(" if messages == [] else None
            return render_dashboard(status=None, messages=messages, messages_component_status=status)
    return render_dashboard(status=None, messages_component_status="Invalid passcode", messages=None)

@app.route("/retrieve_messages", methods=['POST'])
def retrieve_messages_route():
    return retrieve_messages()
