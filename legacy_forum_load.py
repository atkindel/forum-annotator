#!/usr/bin/env python

import sys
import time
import os
from csv import DictReader
from dbutils import with_db, query

def to_epoch(timestamp):
    '''Convert post timestamp string to epoch time.'''
    if not timestamp:
        return "0"
    else:
        try:
            return str(int(time.mktime(time.strptime(timestamp, '%Y-%m-%d %H:%M:%S.%f %Z'))))
        except ValueError:
            return str(int(time.mktime(time.strptime(timestamp, '%Y-%m-%d %H:%M:%S %Z'))))

dbms = {'username': os.environ['DB_USER'],
        'password': os.environ['DB_PASS'],
        'db': os.environ['DB_NAME'],
        'host': os.environ['DB_HOST'],
        'port': int(os.environ['DB_PORT'])}

@with_db(dbms)
def load(db):
    with open(sys.argv[1]) as t:
        rows = DictReader(t)
        rowct = 0
        for row in rows:
            row['body'] = row['body'].replace('"', '""')
            row['title'] = row['title'].replace('"', '""')
            row.pop('upvotes')
            for key in row.keys():
                if key not in ['created_at', 'updated_at', 'level', 'comment_count', 'author_id', 'finished', 'pinned', 'anonymous']:
                    row[key] = '"%s"' % row[key]
                elif row[key] in ['NA', '0', 'False']:
                    row[key] = str(0)
            if not row['pinned']:
                row['pinned'] = str(0)
            row['created_at'] = to_epoch(row['created_at'])
            row['updated_at'] = to_epoch(row['updated_at'])
            q = "INSERT INTO threads(%s) VALUES (%s)" % (','.join(row.keys()), ','.join(row.values()))
            query(db, q)
            rowct += 1
        print "Loaded %d forum posts to annotator." % rowct

if __name__ == "__main__":
    load()
