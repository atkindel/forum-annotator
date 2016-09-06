#!/usr/bin/env python
# annotator.py
# Core logic for forum data annotator application.
#
# Author: Alex Kindel
# Date: 19 July 2016

from csv import DictReader
from functools import wraps
import subprocess
import time
import os

from flask import Flask, g, render_template, request, url_for, redirect, session, flash
from werkzeug import generate_password_hash, check_password_hash
from dbutils import with_db, query


# Configuration
DEV_INSTANCE = True
THREADS = 'data/threads.csv'
SECRET_KEY = os.environ['SECRET_KEY']

# Create application container
application = Flask(__name__)
application.config.from_object(__name__)
dbms = {'username': os.environ['DB_USER'],
        'password': os.environ['DB_PASS'],
        'db': os.environ['DB_NAME'],
        'host': os.environ['DB_HOST'],
        'port': int(os.environ['DB_PORT'])}


# Static helper methods

def to_epoch(timestamp):
    '''Convert post timestamp string to epoch time.'''
    return str(int(time.mktime(time.strptime(timestamp, '%Y-%m-%d %H:%M:%S'))))


# Database procedures

@with_db(dbms)
def total_posts(db, thread_id):
    return query(db, "SELECT count(*) FROM threads WHERE comment_thread_id = '%s'" % thread_id).next().values()[0] + 1

@with_db(dbms)
def done_posts(db, user_id, thread_id):
    return query(db, "SELECT done FROM assignments WHERE user_id = %d AND thread_id = '%s'" % (user_id, thread_id)).next().values()[0]

@with_db(dbms)
def set_finished(db, user_id, thread_id):
    query(db, "UPDATE assignments SET finished = 1 WHERE thread_id = '%s' and user_id = %d" % (thread_id, user_id))


# Clickstream logging

@application.before_request
def log():
    # TODO: Implement user interaction logging
    # The server might want to tarball these logfiles periodically
    pass


# Database management

@application.cli.command('build')
def build_db():
    '''Rebuild MySQL tables for development.'''
    # XXX: Don't use this in production
    if DEV_INSTANCE:
        subprocess.call("mysql -h %s -P %d -D %s -u %s -p%s < ./sql/schema.sql" % (dbms['host'], dbms['port'], dbms['name'], dbms['username'], dbms['password']), shell=True)


@application.cli.command('load')
@with_db(dbms)
def load_db(db):
    with open(application.config['THREADS']) as t:
        rows = DictReader(t)
        rowct = 0
        for row in rows:
            row['body'] = row['body'].replace('"', '""')
            for key in row.keys():
                if key not in ['created_at', 'updated_at', 'level', 'comment_count', 'author_id', 'finished', 'pinned', 'anonymous']:
                    row[key] = '"%s"' % row[key]
                elif row[key] in ['NA', '0', 'False']:
                    row[key] = str(0)
            if not row['pinned']:
                row['pinned'] = str(0)
            row['created_at'] = to_epoch(row['created_at'])
            row['updated_at'] = to_epoch(row['updated_at'])
            query(db, "INSERT INTO threads(%s) VALUES (%s)" % (','.join(row.keys()), ','.join(row.values())))
            rowct += 1
        print "Loaded %d forum posts to annotator." % rowct


# User session management

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

@application.before_request
@with_db(dbms)
def set_user(db):
    '''Attach user information to HTTP requests.'''
    g.user = None
    if 'user_id' in session:
        try:
            g.user = query(db, "SELECT id, username, first_name, last_name, superuser FROM users WHERE id = %s" % session['user_id']).next()
        except StopIteration:
            session.clear()
            g.user = query(db, "SELECT id, username, first_name, last_name, superuser FROM users WHERE id = %s" % session['user_id']).next()



@application.route('/login', methods=['GET', 'POST'])
@with_db(dbms)
def login(db):
    '''Log in as user.'''
    if g.user:
        return redirect(url_for('index'))
    if request.method == 'POST':
        user = None
        try:
            user = query(db, "SELECT id, pass_hash FROM users WHERE username = '%s'" % request.form['username']).next()
        except StopIteration:
            pass
        if not user:
            flash("Invalid username.")
        elif not check_password_hash(user['pass_hash'], request.form['password']):
            flash("Invalid password.")
        else:
            session['user_id'] = user['id']
            return redirect(url_for('index'))
    return render_template('login.html')

@application.route('/logout')
def logout():
    '''Logout active user.'''
    session.pop('user_id', None)
    return redirect(url_for('index'))

@application.route('/<username>')
@login_required
@with_db(dbms)
def userpage(db, username):
    '''Show assignment information for this user.'''
    user_id = g.user['id']
    assignments = query(db, "SELECT * FROM assignments WHERE user_id = %d" % user_id, fetchall=True)
    return render_template('user.html', username=username, assignments=assignments)

@application.route('/admin', methods=['GET', 'POST'])
@with_db(dbms)
def admin(db):
    '''Logic for user admin page'''
    if request.method == 'POST':
        su = int(request.form.get('superuser') == 'on')
        query(db, "INSERT INTO users(username, first_name, last_name, email, pass_hash, superuser) VALUES ('%s','%s','%s','%s','%s','%s')" %
                  (request.form['username'], request.form['first_name'], request.form['last_name'], request.form['email'], generate_password_hash(request.form['password']), su))
        return redirect(url_for('admin'))
    users = query(db, 'select id, username, first_name, last_name, superuser from users', fetchall=True)
    return render_template('admin.html', users=users)


# Annotator administration

@with_db(dbms)
def assigned(db, thread_id, user_id):
    assns = query(db, "SELECT 1 FROM assignments WHERE thread_id = '%s' AND user_id = %d" % (thread_id, int(user_id)), fetchall=True)
    return bool(assns)

@application.context_processor
def assignment_processor():
        # should this be specific to code_type? -MY
    '''Template utility function: is thread_id assigned to user_id?'''
    def fn(thread_id, user_id):
        return assigned(thread_id, user_id)
    return dict(assigned=fn)

@application.context_processor
@with_db(dbms)
def done_processor(db):
        # should this be specific to code_type? -MY
    '''Template utility function: how many posts in thread X has user Y coded?'''
    def done(thread_id, user_id):
        ct = done_posts(user_id, thread_id)
        total = total_posts(thread_id)
        return "%d/%d" % (ct, total)
    return dict(done=done)


@application.route('/assign', methods=['GET', 'POST'])
@with_db(dbms)
def assign(db):
    '''Logic for thread assigner'''
    threads = query(db, "SELECT mongoid, title FROM threads WHERE level = 1", fetchall=True)
    users = query(db, "SELECT id, first_name, last_name FROM users ORDER BY id", fetchall=True)
    code_type = "replymap"  # Hard-coded, but should be generalized for other coder tasks
    if request.method == 'POST':
        for key in request.form.keys():
            ids = eval(key)
            value = request.form[key]
            thread = ids['thread']
            user = ids['user']
            if value == 'on' and not assigned(thread, user):
                query(db, "INSERT INTO assignments(thread_id, user_id, code_type, next_post, finished) VALUES ('%s','%s','%s','%s','%s')" % (thread, user, code_type, thread, 0))
    return render_template('assignments.html', users=users, threads=threads)

@application.route('/tables/<tablename>/<limit>')
@application.route('/tables/<tablename>')
@superuser_required
@with_db(dbms)
def tables(db, tablename, limit='100'):
    '''Display route for database tables. For debugging purposes.'''
    table = query(db, "SELECT * FROM %s LIMIT %s" % (tablename, limit), fetchall=True)
    header = table[0].keys()
    return render_template('tables.html', tablename=tablename, table=table, header=header)


# Annotator user views

@with_db(dbms)
def get_thread(db, threadid):
    '''Given a top-level post mongoid, return the corresponding thread.'''
    return query(db, "SELECT * FROM threads WHERE mongoid = '%s' UNION ALL SELECT * FROM threads WHERE comment_thread_id = '%s'" % (threadid, threadid), fetchall=True)

def fetch_posts(threadid, next_post_id):
    '''Fetch all posts completed up to mongoid of next post within the main reply sub-group.'''
    thread = get_thread(threadid) # shouldn't this have a db argument? Or does @with_db take care of it?
    parent_id = query(db, "SELECT parent_ids FROM threads WHERE mongoid = '%s'" % (next_post_id).values()[0]
    history = []                  # Want to make sure this isn't sneaking through on some gloabl pass-through for some reason
    for post in thread:
        # before adding, check to see if post is:
        # a) top level-post
        # b) main reply with a mongoid that matches parent_ids of next_post_id
        # c) main reply that matches parent_ids of next_post_id
        if post['level'] == '1':
                history.append(post)
        elif post['mongoid'] == parent_id:
                history.append(post)
        elif post['parent_ids'] == parent_id:
                history.append(post)
        if post['mongoid'] == next_post_id:
            return history[:-1], history[-1]

@with_db(dbms)
def goto_post(db, userid, threadid, rel_idx):
    '''Given a relative index, move persistent pointer to post on deck accordingly.'''
    post_idx = done_posts(userid, threadid) + rel_idx
    if post_idx < 0:
        return "Earliest post."
    elif post_idx >= total_posts(threadid):
        set_finished(userid, threadid)
        return "Last post. This thread is finished!"
    thread = get_thread(threadid)
    post_id = thread[post_idx]['mongoid']
    code_type = "replymap"  # Hard-coded, but should be generalized for other coder tasks
    query(db, "UPDATE assignments SET done = done + %d, next_post = '%s' WHERE thread_id = '%s' AND user_id = %d AND code_type = '%s' " % (rel_idx, post_id, threadid, userid, code_type))
    return None


@application.route('/annotate', methods=['GET', 'POST'])
@login_required
@with_db(dbms)
def annotate(db):
    '''Logic for user annotation of forum posts.'''
    userid = g.user['id']
    assigned = query(db, "SELECT a.thread_id, t.title, a.next_post FROM assignments a JOIN threads t ON thread_id = mongoid WHERE user_id = %d" % userid, fetchall=True)
    if request.method == 'POST':
        threadid = request.form['thread']
        return redirect(url_for('annotate_thread', threadid=threadid))
    return render_template('annotate.html', assigned=assigned)

@application.route('/annotate/<threadid>', methods=['GET', 'POST'])
@login_required
@with_db(dbms)
def annotate_thread(db, threadid):
    userid = g.user['id']
    code_type = "replymap"  # Hard-coded, but should be generalized for other coder tasks
    comments = None
    msg = None
    if request.method == 'POST':
        if 'next' in request.form.keys():
            msg = goto_post(userid, threadid, 1)
        elif 'prev' in request.form.keys():
            msg = goto_post(userid, threadid, -1)
        elif 'code' in request.form.keys():
            code_value = request.form['codevalue']
            if code_value == "blank":
                msg = "Submit a code for this post."
            else:
                comment = request.form['comment']
                postid = request.form['postid']
                comment_ids = None
                if code_value == 'commenters':
                    comment_ids = [request.form[k] for k in request.form.keys() if 'target' in k]
                    targets = '||'.join(comment_ids)
                code_type = "replymap"  # Hard-coded, but should be generalized for other coder tasks
                try:
                    existing = query(db, "SELECT code_id FROM codes WHERE post_id = '%s' AND user_id = %d" % (postid, userid)).next()['code_id']
                except StopIteration:
                    if code_value == 'commenters':
                        if not comment_ids:
                            msg = "Which commenters was this post responding to?"
                        else:
                            query(db, "INSERT INTO codes(user_id, post_id, code_type, code_value, targets, comment) VALUES ('%s', '%s', '%s', '%s', '%s', '%s')" % (userid, postid, code_type, code_value, targets, comment))
                    else:
                        query(db, "INSERT INTO codes(user_id, post_id, code_type, code_value, comment) VALUES ('%s', '%s', '%s', '%s', '%s')" % (userid, postid, code_type, code_value, comment))
                else:
                    if code_value == 'commenters':
                        if not comment_ids:
                            msg = "Which commenters was this post responding to?"
                        else:
                            query(db, "UPDATE codes SET code_value = '%s', comment = '%s', targets = '%s' WHERE code_id = %d" % (code_value, comment, targets, existing))
                    else:
                        query(db, "UPDATE codes SET code_value = '%s', comment = '%s' WHERE code_id = %d" % (code_value, comment, existing))
                finally:
                    if not msg:
                        msg = goto_post(userid, threadid, 1)
        if msg:
            flash(msg)
    next_post_id = query(db, "SELECT next_post FROM assignments WHERE thread_id = '%s' AND user_id = %d AND code_type = '%s'" % (threadid, userid, code_type)).next().values()[0]
    comments = query(db, "SELECT code_value, comment FROM codes WHERE post_id = '%s' AND user_id = %d AND code_type = '%s'" % (next_post_id, userid, code_type), fetchall=True)
    posts, next_post = fetch_posts(threadid, next_post_id)
    return render_template('posts.html', threadid=threadid, posts=posts, next=next_post, comments=comments)


# Main page

@application.route('/')
def index():
    return render_template('index.html')


if __name__ == "__main__":
    application.run()
