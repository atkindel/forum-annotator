# forum-annotator
Web-based tool to scaffold analysis of hierarchically structured text.

## To run locally...

* clone this repo to your machine (`git clone https://github.com/atkindel/forum-annotator.git`)
* create a dedicated virtualenv for this app instance
    * more on this here: https://virtualenvwrapper.readthedocs.io/en/latest/
* configure database access (see below-- recommend using localhost for a local development instance)
* run the configuration script (`./configure.sh`)
    * this should only need to run once per install
* set up the database if needed
    * initialize the schema (`flask build` recreates the schema on the configured database; note that this will overwrite existing data!)
    * load the thread data (`flask load`, presuming the data is available at `./data/threads.csv`)
* start the app (`./annotator.py`)
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
