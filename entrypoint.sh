#!/bin/bash
# This script runs the prediction script continuously, pausing for $DELAY_TIME seconds (default 3600)
# between each run. You can control which options are passed to the script via the PREDICT_OPTS env variable.
# Default delay is set to 3600 seconds (1 hour) if DELAY_TIME is not defined in your environment.
DELAY=${DELAY_TIME:-3600}
OPTS=${PREDICT_OPTS:---predict --narrate --commit --deploy}

while true; do
    python nordpool_predict_fi.py $OPTS
    echo "Script completed. Sleeping for ${DELAY} seconds..."
    sleep $DELAY
done