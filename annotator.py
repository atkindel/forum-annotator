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
        totct = 0
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
                    post['body'] = post['body'].replace('"', '""').decode('utf-8').encode('utf-8')
                    for key in post.keys():
                        if key not in ['created_at', 'updated_at', 'level', 'comment_count', 'author_id', 'finished', 'pinned', 'anonymous']:
                            post[key] = '"%s"' % post[key]
                        if post[key] in ['NA', '0', 'False']:
                            post[key] = str(0)
                        if key in ['created_at', 'updated_at']:
                            post[key] = to_epoch(post[key])

                    # Load to database
                    query(db, "SET NAMES utf8mb4;")  # Handle 4-byte UTF-8 characters, e.g. emoji
                    query(db, "INSERT INTO posts(%s) VALUES (%s)" % (','.join(post.keys()), ','.join(post.values())))
                    rowct += 1
                    totct += 1
                    post_ids[row['mongoid']] = totct  # Store mongoid-postid mapping

                    # If this is the first post in the thread, update thread metadata
                    if row['mongoid'] == mongoid:
                        query(db, "UPDATE threads SET first_post_id = (SELECT count(*)+1 FROM posts) WHERE mongoid = '%s'" % mongoid)
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
        # Get task options and parameters
        nav = int(request.form.get('allow_navigation') == 'on')
        cmnts = int(request.form.get('allow_comments') == 'on')
        opts_data = request.form.get('options').split('\r\n')
        opts = list()
        restr = list()
        for i, opt in enumerate(opts_data):
            if any(map(lambda x: x in opt, ['<', '>', '='])):
                opt, rs = opt.rsplit(' ', 1)
                restr.append(rs)
            else:
                restr.append("_")
            opts.append(opt.strip('"').replace("'", "`"))
        opts = '||'.join(opts)
        restr = '||'.join(restr)

        # Record task data
        query(db, "INSERT INTO tasks(title, label, display, prompt, type, options, restrictions, allow_comments, allow_navigation) VALUES ('%s','%s','%s','%s','%s','%s','%s','%s','%s')" %
              (request.form['title'], request.form['label'], request.form['display'], request.form['prompt'], request.form['type'], opts, restr, cmnts, nav))
        return redirect(url_for('tasks'))
    tasks = query(db, "SELECT * FROM tasks", fetchall=True)
    return render_template("tasks.html", tasks=tasks)

# TODO: Make this more useful
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
        return redirect(url_for('annotate_thread', assn_id=assn_id))
    return render_template('annotate.html', assigned=assignments)

@with_db(dbms)
def retrieve_thread(db, thread_id, next_post_id):
    '''Fetch all posts in context up to next post.'''
    parent_post_id = query(db, "SELECT parent_post_id FROM posts WHERE post_id = %s" % next_post_id, fetchall=True)[0]['parent_post_id']
    q = ("select * from posts where thread_id = {0} and level = 1 "  # Top-level post
         "union all select * from posts where post_id = {1} "  # Main reply
         "union all select * from posts where parent_post_id = {1} and post_id < {2} and level > 2 "  # Previous commenters
         "union all select * from posts where post_id = {2}"  # Next post to code
         ).format(thread_id, parent_post_id, next_post_id)
    thread = query(db, q, fetchall=True)

    # Return top-level post, previous replies in context, next post to code
    return thread[0], thread[1:-1], thread[-1]

@with_db(dbms)
def goto_post(db, assn_id, coded_post_id, rel_idx):
    '''Move persistent pointer to next pointer by value of rel_idx'''
    # Bound navigation
    bounds = query(db, "SELECT a.done, t.comment_count FROM assignments a JOIN threads t ON a.thread_id = t.thread_id WHERE assn_id = %s" % assn_id, fetchall=True)[0]
    if bounds['done'] == bounds['comment_count']:
        query(db, "CALL set_finished(%s)" % assn_id)
        return "Last post. This thread is finished!"
    elif bounds['done'] + rel_idx < 0:
        return "First post."

    # Identify ID of next post
    vals = query(db, "SELECT level, parent_post_id FROM posts WHERE post_id = %s" % coded_post_id, fetchall=True)[0]
    level, ppi = vals['level'], vals['parent_post_id']
    try:
        if level == 2:
            new_next_post_id = query(db, "SELECT post_id FROM posts WHERE parent_post_id = %s AND level = 3" % coded_post_id, fetchall=True)[0]['post_id']  # Step down into subthread, if exists
    except:
        new_next_post_id = query(db, "SELECT post_id FROM posts WHERE post_id > %s AND level = 2" % coded_post_id, fetchall=True)[0]['post_id']  # Get next main reply if no subthread
    try:
        if level >= 3:
            new_next_post_id = query(db, "SELECT post_id FROM posts WHERE parent_post_id = %s AND post_id > %s AND level > 3 LIMIT 1" % (ppi, coded_post_id), fetchall=True)[0]['post_id']  # Get next L4 reply
    except:
        new_next_post_id = query(db, "SELECT post_id FROM posts WHERE post_id > %s AND level = 2 LIMIT 1" % ppi, fetchall=True)[0]['post_id']  # Go to next main reply if we hit bottom of subthread

    # Update assignment pointer
    query(db, "UPDATE assignments SET done = done + %d, next_post_id = %s WHERE assn_id = %s" % (rel_idx, new_next_post_id, assn_id))
    return None

def handle_replymap(form, method, codes):
    '''Special processing for reply mapping view'''
    if method == "replymap" and "commenters" in codes:
        comment_ids = [request.form[k] for k in request.form.keys() if 'target' in k]
        return '||'.join(comment_ids)
    else:
        return ""

@application.route('/annotate/<assn_id>', methods=['GET', 'POST'])
@login_required
@with_db(dbms)
def annotate_thread(db, assn_id):
    user_id = g.user['id']

    # Retrieve task parameters
    task = query(db, "SELECT * FROM tasks WHERE task_id = (SELECT task_id FROM assignments WHERE assn_id = %s)" % assn_id, fetchall=True)[0]

    # Handle code submissions, code updates, navigation
    msg = None
    while request.method == 'POST':
        # Just coded post_id
        coded_post_id = query(db, "SELECT * FROM assignments WHERE assn_id = %s" % assn_id, fetchall=True)[0]['next_post_id']

        # Handle navigation events, mostly for debugging
        if 'next' in request.form.keys():
            msg = goto_post(assn_id, coded_post_id, 1)
            break

        # Parse submitted code values
        code_values = [request.form[c] for c in request.form.keys() if 'choice' in c]
        if "no_code" in code_values or not code_values:
            msg = "Submit a code for this post."
            break  # Reject if no code submitted
        code = "||".join(code_values)

        # Parse user comments
        comment_text = ""
        if task['allow_comments']:
            comment_text = request.form['comment'].replace("`", "").replace("'", "`")  # This replace 'safely' handles contractions

        # Parse targets for replymap task
        targets = handle_replymap(request.form, task['display'], code_values)
        if not targets and "commenters" in code_values:
            msg = "Which commenters was this post responding to?"
            break  # Reject if no targets identified

        # If code already exists, move to revisions table and drop from canon
        try:
            existing = query(db, "SELECT * FROM codes WHERE post_id = %s AND user_id = %d AND assn_id = %s" % (coded_post_id, user_id, assn_id)).next()['code_id']
            if existing:
                query(db, "INSERT INTO revised SELECT * FROM codes WHERE code_id = %s" % existing)
                query(db, "DELETE FROM codes WHERE code_id = %s" % existing)
        except StopIteration:
            pass  # Move on if no existing code

        # Append code to table
        query(db, "INSERT INTO codes(user_id, post_id, assn_id, code_value, targets, comment) VALUES ('%s', '%s', '%s', '%s', '%s', '%s')" % (user_id, coded_post_id, assn_id, code, targets, comment_text))
        msg = goto_post(assn_id, coded_post_id, 1)  # Advance next post pointer
        break

    # Display alerts to user if something bad happened
    if msg:
        flash(msg)

    # Fetch most up-to-date assignment data
    assignment = query(db, "SELECT * FROM assignments WHERE assn_id = %s" % assn_id, fetchall=True)[0]
    next_post_id = assignment['next_post_id']
    thread_id = assignment['thread_id']

    # Pull thread data to display and code
    comments = query(db, "SELECT code_value, comment FROM codes WHERE post_id = %s AND user_id = %d AND assn_id = %s" % (next_post_id, user_id, assn_id), fetchall=True)
    top_level_post, prev_posts, next_post = retrieve_thread(thread_id, next_post_id)

    return render_template('code.html', task=task, assn_id=assn_id, thread_id=thread_id, tlp=top_level_post, prev=prev_posts, next=next_post, comments=comments)


# Tiebreaking view

@application.route('/tiebreaker')
@superuser_required
@with_db(dbms)
def tiebreak(db):
    pass


# Main page

@application.route('/')
def index():
    return render_template('index.html')


if __name__ == "__main__":
    application.run()
