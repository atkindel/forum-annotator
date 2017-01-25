#!/usr/bin/env python

import requests
import sys
import time
from bs4 import BeautifulSoup

# Fetch data
raw = None
pars = {"t": "all",
        "limit": int(sys.argv[2])}
while True:
    r = requests.get("http://www.reddit.com/r/" + str(sys.argv[1]) + "/top/", params=pars)
    status = r.status_code
    if status == 200:
        raw = r.text
        break
    else:
        time.sleep(3)

# Parse thread comment links
threads = ""
soup = BeautifulSoup(raw, 'html.parser')
for a in soup.find_all("a"):
    if "comments" in a.get("class", list()):
        thread_id = a.get("href").split("/")[6]
        if thread_id:
            threads += thread_id + " "

print "(%s)" % threads.rstrip(" ")
