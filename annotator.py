# annotator.py
# Core logic for forum data annotator application.
# 
# Author: Alex Kindel
# Date: 19 July 2016

from csv import DictReader
from functools import wraps
import time

from flask import Flask, g, render_template, request, url_for, redirect, session
from werkzeug import generate_password_hash, check_password_hash
import sqlite3


# Configuration
DATABASE = "data/annotator.db"
SECRET_KEY = "DEBUG"
THREADS = "data/threads.csv"

# Create application container
app = Flask(__name__)
app.config.from_object(__name__)


## Helper methods

def to_epoch(timestamp):
	return str(int(time.mktime(time.strptime(timestamp, '%Y-%m-%d %H:%M:%S'))))
	

## Database management

def open_db():
	if not hasattr(g, 'sqlite_db'):
		g.sqlite_db = sqlite3.connect(app.config['DATABASE'])
		g.sqlite_db.row_factory = sqlite3.Row  # treat db rows as dicts
	return g.sqlite_db

@app.cli.command('build')
def build_db():
	db = open_db()
	with open('sql/schema.sql') as f:
		db.executescript(f.read())
	db.commit()

@app.cli.command('load')
def load_db():
	db = open_db()
	with open(app.config['THREADS']) as t:
		rows = DictReader(t)
		rowct = 0
		for row in rows:
			row['body'] = row['body'].replace('"','""')
			for key in row.keys():
				if key not in ['created_at', 'updated_at', 'level', 'comment_count', 'author_id', 'finished']:
					row[key] = '"%s"' % row[key]
				elif row[key] in ['NA', '0']:
 					row[key] = str(0)
			row['created_at'] = to_epoch(row['created_at'])
			row['updated_at'] = to_epoch(row['updated_at'])
			query = "INSERT INTO threads(%s) VALUES (%s)" % (','.join(row.keys()), ','.join(row.values()))
			db.execute(query)
			db.commit()
			rowct += 1
		print "Loaded %d forum posts to annotator." % rowct

@app.teardown_appcontext
def close_db(error):
	if hasattr(g, 'sqlite_db'):
		g.sqlite_db.close()


## User session management

def login_required(f):
	'''Require logged-in user to access.'''
	@wraps(f)
	def login_req_fn(*args, **kwargs):
		if not g.user:
			return redirect(url_for('login'))
		return f(*args, **kwargs)
	return login_req_fn
	
def superuser_required(f):
	'''Required logged-in superuser to access.'''
	@wraps(f)
	def su_req_fn(*args, **kwargs):
		if not g.user:
			return redirect(url_for('login'))
		if not g.user['superuser']:
			return redirect(url_for('index'))
		return f(*args, **kwargs)
	return su_req_fn
	
@app.before_request
def set_user():
	'''Attach user information to HTTP requests.'''
	g.user = None
	if 'user_id' in session:
		db = open_db()
		g.user = db.execute("SELECT * FROM users WHERE id = ?", [session['user_id']]).fetchone()
	
@app.route('/login', methods=['GET', 'POST'])
def login():
	'''Log in as user.'''
	if g.user:
		return redirect(url_for('index'))
	if request.method == 'POST':
		db = open_db()
		user = db.execute("SELECT * FROM users WHERE username = ?", [request.form['username']]).fetchone()
		if not user:
			print "Invalid username."
		elif not check_password_hash(user['pass_hash'], request.form['password']):
			print "Invalid password."
		else:
			session['user_id'] = user['id']
			return redirect(url_for('index'))
	return render_template('login.html')

@app.route('/logout')
def logout():
	'''Logout active user.'''
	session.pop('user_id', None)
	return redirect(url_for('index'))

@app.route('/admin', methods=['GET', 'POST'])
def admin():
	'''Logic for user admin page'''
	if request.method == 'POST':
		db = open_db()
		su = (request.form.get('superuser') == 'on')
		db.execute("insert into users(username, first_name, last_name, email, pass_hash, superuser) values (?,?,?,?,?,?)",
			  [request.form['username'], request.form['first_name'], request.form['last_name'], request.form['email'], generate_password_hash(request.form['password']), su])
		db.commit()
		return redirect(url_for('admin'))
	db = open_db()
	users = db.execute('select id, username, first_name, last_name, superuser from users').fetchall()
	return render_template('admin.html', users=users)


## Annotator administration

def assigned(thread_id, user_id):
	db = open_db()
	assns = db.execute("SELECT * FROM assignments WHERE thread_id = '%s' AND user_id = %d" % (thread_id, int(user_id))).fetchall()
	return bool(assns)

@app.context_processor
def assignment_processor():
	'''Template utility function: is thread_id assigned to user_id?'''
	def fn(thread_id, user_id):
		return assigned(thread_id, user_id)
	return dict(assigned=fn)
	
@app.context_processor
def done_processor():
	''' Template utility function: how many posts in thread X has user Y coded?'''
	def done(thread_id, user_id):
		db = open_db()
		ct = db.execute("SELECT done FROM assignments WHERE thread_id = '%s' AND user_id = %d" % (thread_id, int(user_id))).fetchone()[0]
		total = db.execute("SELECT count(*) FROM threads WHERE comment_thread_id = '%s'" % thread_id).fetchone()[0]
		return "%d/%d" % (ct, total)
	return dict(done=done)

@app.route('/assign', methods=['GET', 'POST'])
def assign():
	'''Logic for thread assigner'''
	db = open_db()
	threads = db.execute("SELECT mongoid, title FROM threads WHERE level = 1").fetchall()
	users = db.execute("SELECT * FROM users ORDER BY id").fetchall()
	if request.method == 'POST':
		for key in request.form.keys():
			ids = eval(key)
			value = request.form[key]
			thread = ids['thread']
			user = ids['user']
			if value == 'on' and not assigned(thread, user):
				db.execute("INSERT INTO assignments(thread_id, user_id, next_post, finished) VALUES (?,?,?,?)", [thread, user, thread, 0])
				db.commit()
	return render_template('assignments.html', users=users, threads=threads)


## Main page

@app.route('/')
def index():
	return render_template('index.html')


if __name__ == "__main__":
    app.run()