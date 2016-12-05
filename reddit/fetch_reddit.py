#!/usr/bin/env python

import requests
import sys
import time

# Fetch data
while True:
    r = requests.get("http://www.reddit.com/r/Republican/comments/" + sys.argv[1])
    status = r.status_code
    if status == 200:
        print r.text.encode('utf-8')
        break
    else:
        time.sleep(3)
