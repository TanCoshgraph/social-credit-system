from flask import (
    Flask as flask, 
    render_template,
    redirect,
    request,
    session,
    g
)
import pickle
import uuid

app = flask(__name__)

class Person:
    def __init__(self, name, score=0):
        self.id = str(uuid.uuid4())
        self.name = name
        self.score = score

def initialize_me():
    people = {}
    print('trying to initialize')
    try:
        with open('people', 'rb') as f:
            people = pickle.load(f)
        if people is None or people == []:
            re_init_people()
    except:
        re_init_people()

def re_init_people():
    temp = [Person("Sean"), Person("Rebecca"), Person("Dan")]
    people = {}
    for person in temp:
        people[person.id] = person
    with open('people', 'wb') as f:
        pickle.dump(people, f)
    return people

def get_people():
    try:
        with open('people', 'rb') as f:
            people = pickle.load(f)
        if people is None or people == [] or people == {}:
            re_init_people()
    except:
        return re_init_people()
    return people

@app.route("/")
def hello_world():
    people = get_people()
    return render_template('scoreboard.html', rows=people)

def save_people(people):
    with open('people', 'wb') as f:
        pickle.dump(people, f)

@app.route("/increment", methods=['GET'])
def increment():
    people = get_people()
    id = request.args.get('id')
    people[id].score += 5
    save_people(people)
    return redirect('/')

@app.route("/decrement", methods=['GET'])
def decrement():
    people = get_people()
    id = request.args.get('id')
    people[id].score -= 5
    save_people(people)
    return redirect('/')

initialize_me()
