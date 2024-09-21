#!/bin/bash

# Real API with Simple
# python mm.py \
#     --market-ticker FEDDECISION-24NOV-C26 \
#     --trade-side yes \
#     --log-level INFO \
#     --dt 3.0 \
#     --max-position 10 \
#     --spread 0.10 \
#     --order-expiration 60

# Real API with Avellaneda
# python mm.py \
#     --market-ticker FEDDECISION-24NOV-C26 \
#     --trade-side yes \
#     --log-level INFO \
#     --dt 4.0 \
#     --max-position 10 \
#     --order-expiration 60

# Simulated API with Avellaneda
# python mm.py \
#     --market-ticker FEDDECISION-24NOV-C26 \
#     --trade-side yes \
#     --log-level INFO \
#     --dt 0.01 \
#     --max-position 10 \
#     --order-expiration 60

# Simulated API with Simple
python mm.py \
    --market-ticker FEDDECISION-24NOV-C26 \
    --trade-side yes \
    --log-level INFO \
    --dt 0.1 \
    --max-position 10 \
    --spread 0.10 \
    --order-expiration 60