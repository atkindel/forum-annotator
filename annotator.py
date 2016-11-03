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
from dbutils import with_db, query, dev_only


# Application container
application = Flask(__name__)


# Configuration
DEV_INSTANCE = True
THREADS = 'data/threads.csv'
SECRET_KEY = os.environ['SECRET_KEY']
dbms = {'username': os.environ['DB_USER'],
        'password': os.environ['DB_PASS'],
        'db': os.environ['DB_NAME'],
        'host': os.environ['DB_HOST'],
        'port': int(os.environ['DB_PORT'])}
application.config.from_object(__name__)


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
    assignments = query(db, "SELECT a.user_id, a.task_id, a.thread_id, t.label FROM assignments a JOIN tasks t ON a.task_id = t.task_id WHERE user_id = %d" % user_id, fetchall=True)
    return render_template('user.html', username=username, assignments=assignments)

@application.route('/admin', methods=['GET', 'POST'])
@superuser_required
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


# Database funcs/procs interface

@with_db(dbms)
def total_posts(db, thread_id):
    return query(db, "SELECT total_posts('%s')" % thread_id).next().values()[0]

@with_db(dbms)
def done_posts(db, assignmentid):
    return query(db, "SELECT done_posts('%s')" % assignmentid).next().values()[0]

@with_db(dbms)
def set_finished(db, assignmentid):
    query(db, "CALL set_finished('%s')" % assignmentid)

@with_db(dbms)
def title_of_thread(db, thread_id):
    return query(db, "SELECT thread_title('%s')" % thread_id).next().values()[0]


# Database management

@application.cli.command('build')
def build_db():
    '''Rebuild MySQL tables for development.'''
    subprocess.call("mysql -h %s -P %d -D %s -u %s -p%s < ./sql/schema.sql" % (dbms['host'], dbms['port'], dbms['db'], dbms['username'], dbms['password']), shell=True)
    subprocess.call("mysql -h %s -P %d -D %s -u %s -p%s < ./sql/procs_funcs.sql" % (dbms['host'], dbms['port'], dbms['db'], dbms['username'], dbms['password']), shell=True)

@application.cli.command('load')
@with_db(dbms)
def load_db(db):

    # Static methods for loading
    def assign(target, source, key):
        target[key] = source[key]

    def to_epoch(timestamp):
        '''Convert post timestamp string to epoch time.'''
        return str(int(time.mktime(time.strptime(timestamp, '%Y-%m-%d %H:%M:%S'))))

    with open(application.config['THREADS']) as t:
        rows = DictReader(t)

        # Load threads first
        threadct = 0
        thread_ids = dict()
        for row in rows:
            if row['X_type'] != "CommentThread":
                continue
            else:
                thread = dict()

                # Extract thread data and clean up
                thread['title'] = '"%s"' % row['title']
                thread['body'] = '"%s"' % row['body'].replace('"', '""')
                thread['creator'] = '"%s"' % row['author_username']
                thread['comment_count'] = row['comment_count']
                thread['mongoid'] = '"%s"' % row['mongoid']

                # Load to database
                query(db, "INSERT INTO threads(%s) VALUES (%s)" % (','.join(thread.keys()), ','.join(thread.values())))
                threadct += 1
                thread_ids[row['mongoid']] = threadct  # Store mongoid-threadid mapping
        print "Loading %d threads to annotator." % threadct

        # Load posts for each thread
        for mongoid in thread_ids.keys():
            thread_id = thread_ids[mongoid]
            rowct = 0
            post_ids = dict()
            t.seek(0)  # Reset CSV file head to top
            for row in rows:
                if mongoid not in [row['comment_thread_id'], row['mongoid']]:
                    continue
                else:
                    post = dict()

                    # Extract post data
                    map(lambda x: assign(post, row, x), ['mongoid', 'author_id', 'author_username', 'body', 'level', 'created_at', 'updated_at'])

                    # Map context IDs
                    post['thread_id'] = thread_id
                    post['parent_post_id'] = post_ids.get(row['parent_ids'], -1)

                    # Clean up post data
                    post['body'] = post['body'].replace('"', '""')
                    for key in post.keys():
                        if key not in ['created_at', 'updated_at', 'level', 'comment_count', 'author_id', 'finished', 'pinned', 'anonymous']:
                            post[key] = '"%s"' % post[key]
                        if post[key] in ['NA', '0', 'False']:
                            post[key] = str(0)
                        if key in ['created_at', 'updated_at']:
                            post[key] = to_epoch(post[key])

                    # print "INSERT INTO posts(%s) VALUES (%s)" % (','.join(post.keys()), ','.join(post.values()))

                    # Load to database
                    query(db, "INSERT INTO posts(%s) VALUES (%s)" % (','.join(post.keys()), ','.join(post.values())))
                    rowct += 1
                    post_ids[row['mongoid']] = rowct  # Store mongoid-postid mapping

                    # If this is the first post in the thread, update thread metadata
                    if row['mongoid'] == mongoid:
                        query(db, "UPDATE threads SET first_post_id = (SELECT count(*) FROM posts) WHERE mongoid = '%s'" % mongoid)
            print "Loaded %d forum posts in thread %s to annotator." % (rowct, thread_id)

@application.route('/tables/<tablename>/<limit>')
@application.route('/tables/<tablename>')
@superuser_required
@with_db(dbms)
def tables(db, tablename, limit='100'):
    '''Display route for database tables. For debugging purposes.'''
    table = query(db, "SELECT * FROM %s LIMIT %s" % (tablename, limit), fetchall=True)
    header = table[0].keys()
    return render_template('tables.html', tablename=tablename, table=table, header=header)


# Template context managers

@with_db(dbms)
def assigned(db, thread_id, user_id, task_id):
    assns = query(db, "SELECT 1 FROM assignments WHERE thread_id = %d AND user_id = %d AND task_id = %d" % (int(thread_id), int(user_id), int(task_id)), fetchall=True)
    return bool(assns)

@application.context_processor
def assignment_processor():
    '''Template utility function: is thread_id assigned to user_id?'''
    def fn(thread_id, user_id, task_id):
        return assigned(thread_id, user_id, task_id)
    return dict(assigned=fn)

@application.context_processor
def done_processor():
    '''Template utility function: how many posts in thread X has user Y coded?'''
    @with_db(dbms)
    def done(db, thread_id, user_id, task_id):
        assn_id = query(db, "SELECT assn_id FROM assignments WHERE thread_id = %d AND user_id = %d AND task_id = %d" % (int(thread_id), int(user_id), int(task_id))).next().values()[0]
        count = done_posts(assn_id)
        total = total_posts(thread_id)
        return "%d/%d" % (count, total)
    return dict(done=done)

@application.context_processor
def titleof_processor():
    '''Template utility function: get thread title from threadid'''
    def titleof(thread_id):
        return title_of_thread(thread_id)
    return dict(titleof=titleof)


# Task administration

@application.route('/tasks', methods=['GET', 'POST'])
@superuser_required
@with_db(dbms)
def tasks(db):
    if request.method == 'POST':
        nav = int(request.form.get('allow_navigation') == 'on')
        cmnts = int(request.form.get('allow_comments') == 'on')
        opts = request.form.get('options').replace('\r\n', '||')
        query(db, "INSERT INTO tasks(title, label, display, prompt, type, options, allow_comments, allow_navigation) VALUES ('%s','%s','%s','%s','%s','%s','%s','%s')" %
              (request.form['title'], request.form['label'], request.form['display'], request.form['prompt'], request.form['type'], opts, cmnts, nav))
        return redirect(url_for('tasks'))
    tasks = query(db, "SELECT * FROM tasks", fetchall=True)
    return render_template("tasks.html", tasks=tasks)

@application.route('/tasks/preview/<task_id>')
@superuser_required
@with_db(dbms)
def preview_task(db, task_id):
    sample_thread = query(db, "SELECT * FROM threads LIMIT 1", fetchall=True)[0]
    sample_posts = query(db, "SELECT * FROM posts WHERE thread_id = %d LIMIT 30" % sample_thread['thread_id'], fetchall=True)
    next_post = sample_posts[-1]
    prev_posts = sample_posts[:-1]
    task = query(db, "SELECT * FROM tasks WHERE task_id = %s" % task_id, fetchall=True)[0]
    return render_template("posts/preview.html", task=task, thread=sample_thread, prev=prev_posts, next=next_post)

@application.route('/tasks/assign/<task_id>', methods=['GET', 'POST'])
@superuser_required
@with_db(dbms)
def assign_task(db, task_id):
    '''Logic for task assigner'''
    task = query(db, "SELECT task_id, title FROM tasks WHERE task_id = %s" % task_id, fetchall=True)[0]
    threads = query(db, "SELECT thread_id, title, first_post_id FROM threads", fetchall=True)
    users = query(db, "SELECT id, first_name, last_name FROM users ORDER BY id", fetchall=True)
    if request.method == 'POST':
        for key in request.form.keys():
            ids = eval(key)
            value = request.form[key]
            thread_id = ids['thread']
            user_id = ids['user']
            next_id = ids['next']
            if value == 'on' and not assigned(thread_id, user_id, task_id):
                query(db, "INSERT INTO assignments(thread_id, user_id, task_id, next_post_id, finished) VALUES ('%s','%s','%s','%s','%s')" % (thread_id, user_id, task_id, next_id, 0))
    return render_template('assignments.html', users=users, threads=threads, task=task)


# Annotator user views

@application.route('/annotate', methods=['GET', 'POST'])
@login_required
@with_db(dbms)
def annotate(db):
    '''Dispatch users to annotation interface'''
    userid = g.user['id']
    assignments = query(db, "SELECT a.assn_id, a.thread_id, t.label FROM assignments a JOIN tasks t ON a.task_id = t.task_id WHERE user_id = %d" % userid, fetchall=True)
    if request.method == 'POST':
        assn_id = request.form['assn']
        return redirect(url_for('annotate_thread', assignmentid=assn_id))
    return render_template('annotate.html', assigned=assignments)

# TODO: This method is pretty messy
@with_db(dbms)
def get_thread(db, threadid):
    '''Given a top-level post mongoid, return the corresponding thread.'''
    raw_thread = query(db, "SELECT * FROM threads WHERE mongoid = '%s' UNION ALL SELECT * FROM threads WHERE comment_thread_id = '%s'" % (threadid, threadid), fetchall=True)
    # Split thread into top-level post+main replies and comments
    mainreplies = filter(lambda x: x['level'] <= 2, raw_thread)
    comments = filter(lambda x: x['level'] >= 3, raw_thread)
    thread = []
    for mr in mainreplies:
        # Append main reply
        thread.append(mr)
        pid = mr['mongoid']
        # Immediately append any subreplies to this main reply
        subreplies = filter(lambda x: x['parent_ids'] == pid, comments)
        for subreply in subreplies:
            thread.append(subreply)
    return thread

# TODO: This method is also not great
@with_db(dbms)
def fetch_posts(db, threadid, next_post_id):
    '''Fetch all posts completed up to mongoid of next post.'''
    thread = get_thread(threadid)
    history = []
    next_post = query(db, "SELECT * FROM threads WHERE mongoid = '%s'" % next_post_id, fetchall=True)[0]
    level = next_post['level']
    next_parent_id = None
    if level >= 3:
        next_parent_id = next_post['parent_ids']
    for post in thread:
        if post['mongoid'] == next_post_id:
            return history, next_post
        else:
            post_parent_id = None
            post_level = post['level']
            if post['level'] >= 3:
                post_parent_id = post['parent_ids']
            if ((post_level == 1) or (post_level == 2 and post['mongoid'] == next_parent_id) or (post_level >= 3 and post_parent_id == next_parent_id)) and post['mongoid'] != next_post_id:
                history.append(post)

# TODO: Rewrite this one too
@with_db(dbms)
def goto_post(db, assignmentid, threadid, rel_idx):
    '''Given a relative index, move persistent pointer to post on deck accordingly.'''
    post_idx = done_posts(assignmentid) + rel_idx
    if post_idx < 0:
        return "Earliest post."
    elif post_idx >= total_posts(threadid):
        set_finished(assignmentid)
        return "Last post. This thread is finished!"
    thread = get_thread(threadid)
    post_id = thread[post_idx]['mongoid']
    query(db, "UPDATE assignments SET done = done + %d, next_post = '%s' WHERE assn_id = '%s'" % (rel_idx, post_id, assignmentid))
    return None

# TODO: Decompose POST methods for each coding task
# TODO: This method is a nightmare, holy cow!
@application.route('/annotate/<assignmentid>', methods=['GET', 'POST'])
@login_required
@with_db(dbms)
def annotate_thread(db, assignmentid):
    userid = g.user['id']
    id_vals = query(db, "SELECT code_type, thread_id FROM assignments WHERE assn_id = %d" % int(assignmentid)).next()
    code_type = id_vals['code_type']
    threadid = id_vals['thread_id']
    comments = None
    msg = None
    if request.method == 'POST':
        if 'next' in request.form.keys():
            msg = goto_post(assignmentid, threadid, 1)
        elif 'prev' in request.form.keys():
            msg = goto_post(assignmentid, threadid, -1)
        elif 'code' in request.form.keys():
            code_value = request.form['codevalue']
            if code_value == "blank":
                msg = "Submit a code for this post."
            else:
                comment = request.form['comment'].replace("`", "").replace("'", "`")  # This replace 'safely' handles contractions
                postid = request.form['postid']
                comment_ids = None
                if code_value == 'commenters':
                    comment_ids = [request.form[k] for k in request.form.keys() if 'target' in k]
                    targets = '||'.join(comment_ids)
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
                        msg = goto_post(assignmentid, threadid, 1)
        if msg:
            flash(msg)
    next_post_id = query(db, "SELECT next_post FROM assignments WHERE thread_id = '%s' and user_id = %d AND code_type = '%s'" % (threadid, userid, code_type)).next().values()[0]
    comments = query(db, "SELECT code_value, comment FROM codes WHERE post_id = '%s' AND user_id = %d AND code_type = '%s'" % (next_post_id, userid, code_type), fetchall=True)
    posts, next_post = fetch_posts(threadid, next_post_id)
    return render_template('posts.html', assignmentid=assignmentid, threadid=threadid, posts=posts, next=next_post, comments=comments, codetype=code_type)


# Main page

@application.route('/')
def index():
    return render_template('index.html')


if __name__ == "__main__":
    application.run()
