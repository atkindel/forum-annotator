# forum-annotator
Web-based tool to scaffold analysis of hierarchically structured text.

## To run...

* install Flask (`sudo pip install flask` unless you're on Windows)
* point Flask at the app (from the base directory of the app, `export FLASK_APP=annotator.py`)
* initialize the database (`flask build` places the database at `./data/annotator.db`)
* load the thread data (`flask load`, presuming the data is available at `./data/threads.csv`)
	* (the db/thread paths can be configured from globals `DATABASE` and `THREADS` in `annotator.py`)
* start the app (`flask run`)
* navigate to `localhost:5000/admin` to create a user account
* once you've created a user account you can log in and out and assign threads to that user