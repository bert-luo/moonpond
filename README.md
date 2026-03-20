# moonpond

## Running the Backend with Docker

### Prerequisites

- [Docker](https://www.docker.com/products/docker-desktop/) installed and running
- A `.env` file in the project root with your API keys:
  ```
  ANTHROPIC_API_KEY=sk-moo-...
  ```

### Build

```bash
docker build -t moonpond-backend .
```

This downloads Godot 4.5.1-stable (Linux) and export templates (~1.4 GB) into the image, verifies checksums and version, then installs the Python backend. The first build takes a while (minutes) due to the template download; subsequent builds use Docker layer caching.

### Run

```bash
docker compose up
```

The backend starts at `http://localhost:8000`. Generated games are persisted to the `games/` directory on your host via a volume mount.

### Verify

```bash
# Check Godot is installed correctly inside the container
docker compose exec backend godot --headless --version
# Should print: 4.5.1.stable...

# Check the backend is responding
curl http://localhost:8000/docs
```

### Rebuild

If you change backend code, rebuild and restart:

```bash
docker compose up --build
```