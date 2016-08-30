# forum-annotator
Web-based tool to scaffold analysis of hierarchically structured text.

## To run locally...

* install Flask (`sudo pip install flask` unless you're on Windows)
* point Flask at the app (from the base directory of the app, `export FLASK_APP=annotator.py`)
* set up the database if needed
    * initialize the schema (`flask build` creates the schema on a MySQL instance running on localhost)
    * load the thread data (`flask load`, presuming the data is available at `./data/threads.csv`)
* start the app (`flask run`)
* navigate to `localhost:5000/admin` to create a user account
* once you've created a user account you can log in and out and assign threads to that user

## To configure the database...

* the app expects to find a config file at ~/.aws/forum-annotator
* that file should export the following environment variables:
    * DB_USER
    * DB_PASS
    * DB_NAME (AnnotatorDev for AWS dev instance)
    * DB_HOST (localhost or AWS RDS hostname)
    * DB_PORT (3306 usually)
    * SECRET_KEY (anything will work)
