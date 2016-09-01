#!/bin/bash

# Install dependencies
python setup.py install

# Export environment variables
source ~/.aws/forum_annotator

# Compile stylesheet
lessc ./static/annotator.less ./static/annotator.css
