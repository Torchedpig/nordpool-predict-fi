# Nordpool FI Spot Price Prediction – Containerized Version

**This is a containerized fork of the original Nordpool FI Spot Price Prediction project.**  
The original project was designed as a standalone script. This version automates execution inside Docker, providing an "app" service that runs predictions continuously and a "web" service to serve static files.

> **Note:** For detailed explanations about modeling, data sources, and standalone usage, please refer to the [Original Documentation](https://github.com/vividfog/nordpool-predict-fi/tree/main).

---

## Table of Contents
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Dockerization](#dockerization)
  - [Entrypoint Behavior](#entrypoint-behavior)
  - [Troubleshooting Docker Issues](#troubleshooting-docker-issues)
- [Original Documentation](#original-documentation)
- [License](#license)

---

## Quick Start

This version is designed to run inside Docker and will serve the web UI and data files locally on your machine.

1. **Configure Environment:**  
   Update the `.env.local` file (based on `.env.local.template`) for your environment settings. In particular, adjust:
   
   ```dotenv
   # Delay between successive prediction runs (in seconds)
   DELAY_TIME=3600
   ```

2. **Run Docker Compose:**

   ```bash
   docker-compose up --build
   ```

This command launches two services:
- **app service:** Continuously runs predictions.
- **web service:** Serves static files from the `deploy` folder (via Apache httpd).

---

## Accessing the Web UI Locally

After running `docker-compose up`, the web service will be available at:

- [http://localhost:8500](http://localhost:8500)

By default, the static files (including the UI and all JSON data) are served on port **8500**. You can open this address in your browser to view the prediction dashboard and data.

If you want to change the port, edit the `WEB_PORT` variable in your `.env.local` file (see below) and also update the `docker-compose.yaml` file under the `ports` section for the `web` service to match.

---

## Configuration

All configuration for container behavior is managed via environment variables. For example, `DELAY_TIME` controls the pause between prediction runs. See the [`.env.local.template`](.env.local.template) for more details.

---

## Dockerization

### Entrypoint Behavior

The container runs an `entrypoint.sh` script which:
- Executes the prediction script (`nordpool_predict_fi.py`) with necessary flags.
- Loops indefinitely, sleeping for the duration set by `DELAY_TIME` between runs.

For details on modifying this behavior, view the inline comments at the top of [entrypoint.sh](entrypoint.sh).

### Troubleshooting Docker Issues

Some common Docker issues and solutions:

- **File Permission Errors**:  
  If you see errors such as `"./entrypoint.sh: permission denied"`, verify that:
  - The file is marked executable (`chmod +x entrypoint.sh`).
  - The file uses Unix-style line endings (use `dos2unix entrypoint.sh` if necessary).

- **CORS Errors on the Web Service**:  
  If your browser reports CORS problems, ensure that your `deploy` folder contains an `.htaccess` file with these settings:
  
  ```apacheconf
  <IfModule mod_headers.c>
      Header set Access-Control-Allow-Origin "*"
  </IfModule>
  ```

- **Viewing Logs and Debugging**:  
  Get insights into issues by checking the service logs:
  
  ```bash
  docker-compose logs app
  docker-compose logs web
  ```

---

## Original Documentation

For comprehensive details on the model’s purpose, algorithms, data sources, and the original standalone usage, please consult the [Original Documentation](https://github.com/ORIGINAL_REPO_LINK).  
This containerized version builds on that work, streamlining deployment with Docker.

---

## License

This project is licensed under the MIT License and is provided as-is.

---

*Feel free to copy or adapt this project. A mention or link back to the original repository is appreciated, but not required.*