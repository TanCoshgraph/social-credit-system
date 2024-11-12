from flask import (
    Flask as flask, 
    render_template,
    redirect,
    request,
    session,
    g
)
import pickle
import os
import db

import uuid

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
    def __init__(self, name, score=0, _id=0):
        self.id = _id
        self.name = name
        self.score = score

def create_person_table_db():
    drop_people = 'DROP TABLE IF EXISTS people'
    create_people = 'CREATE TABLE people(id INTEGER PRIMARY KEY NOT NULL, name TEXT NOT NULL, score INTEGER) WITHOUT ROWID'
    connection = db.get_db()
    connection.execute(drop_people)
    connection.execute(create_people)
    connection.commit()

def create_person_db(person):
    connection = db.get_db()

    count = connection.execute('SELECT COUNT(id) FROM people').fetchone()[0]
    get_id = 'SELECT id FROM people ORDER BY id DESC LIMIT 1'
    
    new_id = 1 if count == 0 else connection.execute(get_id).fetchone()[0] + 1

    insert_row = f'INSERT INTO people (id, name, score) VALUES ({new_id},"{person.name}",{person.score})'
    print(insert_row)
    connection.execute(insert_row)
    connection.commit()

def re_init_people():
    temp = [Person("Sean"), Person("Rebecca"), Person("Dan")]
    people = {}
    for person in temp:
        people[person.id] = person
    with open('people', 'wb') as f:
        pickle.dump(people, f)
    return people

def row_to_person(sql_row):
    return Person(sql_row[1], sql_row[2], sql_row[0])

def get_people():
    query = 'SELECT * FROM people'
    connection = db.get_db()
    rows = connection.execute(query).fetchall()
    return list(map(row_to_person, rows))

@app.route("/")
def hello_world():
    people = get_people()
    return render_template('scoreboard.html', rows=people)

@app.route("/increment", methods=['GET'])
def increment():
    people = get_people()
    id = request.args.get('id')
    print(f'They want me to increment Person {id}, but I dont want to right now')
    return redirect('/')

@app.route("/decrement", methods=['GET'])
def decrement():
    people = get_people()
    id = request.args.get('id')
    print(f'They want me to decrement Person {id}, but I dont want to right now')
    return redirect('/')
