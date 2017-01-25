#!/usr/bin/env python

from bs4 import BeautifulSoup
import sys

# Parse comments
soup = None
with open("./raw/republican/" + sys.argv[1] + ".html") as f:
    soup = BeautifulSoup(f.read().replace("\n", " "), 'html.parser')
for p in soup.find_all("p"):
    if not p.get('class'):
        print str(p).replace("<p>", "").replace("</p>", "\n")
