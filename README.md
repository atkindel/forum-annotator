# forum-annotator
Web-based tool to scaffold analysis of hierarchically structured text.

## To run...

`flask build` to initialize the database

`flask load` to load forum data

- Note: the above paths can be configured from globals `DATABASE` and `THREADS` in `annotator.py`.

`flask run` to start the app on `localhost:5000`.