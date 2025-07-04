# Web App backend

### Structure

```
.
├── main.py              # FastAPI server with WebSocket endpoints
├── requirements.txt     # Python dependencies
├── config.py            # Configuration (GCP credentials, Firestore settings)
└── utils/
    ├── ai_client.py     # Wrapper for Vertex AI calls
    ├── stt_client.py    # Speech-to-text streaming helper
    └── db_client.py     # Firestore/BigQuery helper
```
