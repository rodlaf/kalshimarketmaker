#!/bin/bash

python mm.py \
    --market-ticker FEDDECISION-24NOV-C26 \
    --trade-side yes \
    --log-level DEBUG \
    --dt 4.0 \
    --max-position 10 \
    --spread 0.10
    --order-expiration 60
