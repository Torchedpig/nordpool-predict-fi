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

Environment variables related to the machine learning model and Ollama integration:

```dotenv
# Machine Learning Model Configuration
DELAY_TIME=3600          # Delay between predictions (in seconds)
LLM_API_BASE=...        # Base URL for the LLM API
LLM_API_KEY=...         # API key for LLM access
LLM_MODEL=...           # Specific model to use

# Ollama LLM support (for local LLMs)
# Set OLLAMA_API_BASE to your Ollama server, e.g. http://localhost:11434
OLLAMA_API_BASE="http://localhost:11434"
OLLAMA_MODEL="llama3"
```

---

## LLM Provider Options

The backend supports multiple LLM providers for narration generation:

- `openai`: For OpenAI/DeepSeek or any OpenAI-compatible API (set `LLM_API_BASE`, `LLM_MODEL`, `LLM_API_KEY`).
- `ollama`: For local Ollama server (set `OLLAMA_API_BASE`, `OLLAMA_MODEL`).
- `vllm`: For OpenAI-compatible vLLM endpoints (set `VLLM_API_BASE`, `VLLM_MODEL`, `VLLM_MAX_TOKENS`).

Configure the provider in your `.env.local` or `.env.local.template`:

```dotenv
LLM_PROVIDER=openai   # or ollama, or vllm
```

See the `.env.local.template` for all related variables and example values.

---

## LLM Prompt Style Control

You can control the complexity of the prompt sent to the LLM using the environment variable:

```dotenv
SIMPLE_LLM_PROMPT=1  # Use a simple, short prompt (recommended for small/local models)
SIMPLE_LLM_PROMPT=0  # Use the full, detailed prompt (default)
```

If set to `1`, the backend will use a much simpler summary prompt, which is suitable for small or local models (like Ollama or vLLM with limited context). If set to `0`, the full, detailed prompt will be used (recommended for OpenAI/DeepSeek or other large models).

---

## Frontend Production Domain Configuration

You can set the production domain for the web UI via the environment variable:

```dotenv
PRODUCTION_DOMAIN=nordpool-predict-fi.web.app
```

This is used by the frontend scripts to determine when to use the production base URL. If you deploy to a custom domain, set this variable accordingly in your `.env.local` and `.env.local.template`.

---

## LLM Model Attribution in Narration

The backend automatically detects which LLM provider is in use (OpenAI/DeepSeek, Ollama, or vLLM) and always passes the correct model name to the prompt as `MODEL_NAME`. The narration signature line in the generated article will always show the actual model in use, regardless of backend. The prompt template uses `{MODEL_NAME}` as a placeholder, and the backend fills it with the correct value.

**Example:**

- If using Ollama: `*gemma3:1b-it-qat ennustaa vakaan viikon. 💡*`
- If using vLLM: `*google/gemma-3-27b-it ennustaa vakaan viikon. 💡*`
- If using OpenAI/DeepSeek: `*deepseek-chat ennustaa vakaan viikon. 💡*`

No manual changes are needed in the prompt template or environment files for this to work—just set the correct model and provider in your `.env.local`.

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