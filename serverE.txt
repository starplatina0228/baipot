# BAIPOT (Berth Allocation and Prediction Optimization)

This project is a web application for berth allocation and prediction optimization.

## Development Server

To run the development servers for both frontend and backend:

- **Backend:**
  ```bash
  uvicorn backend.main:app --reload
  ```

- **Frontend:**
  ```bash
  cd frontend
  npm run dev
  ```

---

## Guide: Local Backend with GitHub Pages Frontend

This guide explains how to run the backend server on your local machine while using the frontend deployed on GitHub Pages. This process must be followed each time the `ngrok` address changes.

### 1. Start the Backend Server

Open a new terminal and run the following command to start the backend API server.

```bash
# Navigate to the backend directory
cd /home/choi/github/baipot/backend

# Start the server on port 8000
uvicorn main:app --reload --port 8000
```

### 2. Expose Local Server with `ngrok`

Open another new terminal and run the command below to connect your local server (port 8000) to the public internet.

```bash
ngrok http 8000
```

After running, copy the `Forwarding` URL displayed on the screen (e.g., `https://random-string.ngrok-free.app`). **This URL changes every time you restart `ngrok`**.

### 3. Update API Address in Source Code

You must update the new `ngrok` address in the following two files.

#### A. Backend CORS Configuration

- **File:** `/home/choi/github/baipot/backend/main.py`
- **Action:** Add or replace the new `ngrok` address in the `origins` list within the `CORSMiddleware` setup.

```python
# Example
origins = [
    "http://localhost:5173",
    "https://choi.github.io/baipot",
    "https://<your-new-ngrok-address>", // This is the line to edit
]
```

#### B. Frontend API `baseURL`

- **File:** `/home/choi/github/baipot/frontend/src/composables/useSchedule.js`
- **Action:** Replace the `baseURL` in the `axios` instance with your new `ngrok` address.

```javascript
// Example
const api = axios.create({
  baseURL: 'https://<your-new-ngrok-address>', // This is the line to edit
});
```

### 4. Redeploy the Frontend

Once the addresses are updated, run the following command to redeploy the modified frontend to GitHub Pages.

```bash
# Navigate to the frontend directory
cd /home/choi/github/baipot/frontend

# Run the deploy script
npm run deploy
```

### 5. Stopping the Servers

You can stop the running backend server (`uvicorn`) and `ngrok` by pressing `Ctrl + C` in their respective terminals.
