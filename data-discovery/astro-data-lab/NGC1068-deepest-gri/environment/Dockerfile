FROM python:3.13-slim

#Treat /app as the current directory for anything run inside this container
WORKDIR /app

# Starting with the versions of things I have installed in my datalab conda environment
RUN pip install --no-cache-dir \
    astroquery==0.4.11 \
    astropy==8.0.0 \
    pyvo==1.9.1 \
    astro-datalab==2.22.1 \
    pandas==3.0.3 \
    numpy==2.5.0


# curl/jq are useful for the agent to sanity-check TAP endpoints
RUN apt-get update && apt-get install -y --no-install-recommends curl jq \
    && rm -rf /var/lib/apt/lists/*