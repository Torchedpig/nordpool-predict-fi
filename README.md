# Nordpool FI Spot Price Prediction (Containerized)

A Dockerized version of the Nordpool FI Spot Price Prediction project. This version automates predictions and serves a web dashboard, making setup and usage easy for local, LAN, or production environments.

For details on the original model, see the [Original Documentation](https://github.com/vividfog/nordpool-predict-fi/tree/main).

---

## Quick Start

1. **Copy and configure environment variables:**
   - Copy `.env.local.template` to `.env.local`.
   - Edit `.env.local` to set your desired options (see below).

2. **Build and run with Docker Compose:**
   ```bash
   docker-compose up --build
   ```
   This starts two services:
   - `app`: Runs predictions on a schedule.
   - `web`: Serves the dashboard and data (default: [http://localhost:8500](http://localhost:8500)).

---

## Configuration (All in `.env.local`)

All settings are controlled via environment variables. See `.env.local.template` for all options and example values.

**Key options:**
- `DELAY_TIME`: Seconds between prediction runs (default: 3600)
- `WEB_PORT`: Port for the web dashboard (default: 8500)
- `PRODUCTION_DOMAIN`: (Optional) Set if deploying to a custom domain

**LLM Provider Setup:**
- `LLM_PROVIDER`: `openai`, `ollama`, or `vllm`
- For `openai`/compatible: set `LLM_API_BASE`, `LLM_MODEL`, `LLM_API_KEY`
- For `ollama`: set `OLLAMA_API_BASE`, `OLLAMA_MODEL`
- For `vllm`: set `VLLM_API_BASE`, `VLLM_MODEL`, `VLLM_MAX_TOKENS`

**Prompt Style:**
- `SIMPLE_LLM_PROMPT=1` for a short/simple prompt (good for small/local models)
- `SIMPLE_LLM_PROMPT=0` for the full, detailed prompt (default)

**Timezone:**
- `TZ`: Timezone for the container (default: `Europe/Helsinki`). You can override this in `.env.local` or `docker-compose.yaml` if needed. Example: `TZ=UTC`

**FMI Station Configuration:**
- `FMISID_T`: Comma-separated list of FMI station IDs used for temperature data by the **price prediction model**. The main prediction script will automatically attempt to backfill historical data for any new stations listed here that are not already in the database.
- `FMISID_WS`: Comma-separated list of FMI station IDs used for wind speed data by both the **price and wind power prediction models**. Similar to `FMISID_T`, historical data for new stations will be automatically backfilled.
  - The **wind power model** uses wind speed data (`ws_` columns) from FMI stations listed in `FMISID_WS` (plus all `eu_ws_` columns from other European sources).
  - For temperature data (`t_` columns), the **wind power model** uses FMI stations that are common to *both* `FMISID_WS` and `FMISID_T`.
  - If `FMISID_WS` is not set or is empty, the wind power model falls back to using all available `ws_` and `eu_ws_` columns for wind speed, and all available `t_` columns for temperature.
- The system automatically handles the addition of new FMI stations by attempting to backfill historical data. For more control over backfilling (e.g., specific date ranges or for stations not yet added to `.env.local`), you can use the `util/backfill_fmi_data.py` script manually. Execute it from the project root: `python util/backfill_fmi_data.py`. This script will also use the `FMISID_T` and `FMISID_WS` variables from `.env.local` to identify stations if no specific stations are passed as arguments to the script.

---

## LLM Model Attribution

The backend always uses the correct model name in the narration signature, based on your configuration. No manual changes are needed—just set the provider/model in `.env.local`.

---

## Accessing the Dashboard

- Open [http://localhost:8500](http://localhost:8500) (or your chosen `WEB_PORT`) in your browser.
- To change the port, update `WEB_PORT` in `.env.local` and the `ports` section in `docker-compose.yaml`.

---

## Advanced: vLLM & Ollama Support

- **vLLM:**
  - Start a vLLM server with OpenAI-compatible API.
  - Set `LLM_PROVIDER=vllm`, `VLLM_API_BASE`, `VLLM_MODEL`, `VLLM_MAX_TOKENS` in `.env.local`.
- **Ollama:**
  - Start an Ollama server locally.
  - Set `LLM_PROVIDER=ollama`, `OLLAMA_API_BASE`, `OLLAMA_MODEL` in `.env.local`.
- **Switching providers:**
  - Change `LLM_PROVIDER` and the relevant variables. The backend will auto-detect and use the correct settings.

---

## Docker & Troubleshooting

- **Entrypoint:** The container runs predictions in a loop, sleeping for `DELAY_TIME` seconds between runs.
- **File permissions:** If you see `permission denied` errors, ensure `entrypoint.sh` is executable and uses Unix line endings.
- **CORS:** If you get CORS errors, ensure your `deploy/.htaccess` allows all origins.
- **Logs:**
  ```bash
  docker-compose logs app
  docker-compose logs web
  ```

---

## License

MIT License. See [LICENSE](LICENSE).

---

*Feel free to copy or adapt this project. A mention or link back to the original repository is appreciated, but not required.*