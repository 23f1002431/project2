# Quiz Solver Application

An intelligent application that solves data-related quizzes using LLMs, capable of handling data sourcing, preparation, analysis, and visualization tasks.

## Features

- **API Endpoint**: Accepts POST requests with quiz tasks
- **Secret Verification**: Validates requests using a secret string
- **Headless Browser**: Renders JavaScript-heavy quiz pages using Playwright
- **LLM Integration**: Uses the gemini API (or another provider you configure) for task understanding and solving
- **Data Processing**: Handles PDFs, images, text, CSV, and structured data
- **Analysis Capabilities**: Performs filtering, sorting, aggregation, and statistical analysis
- **Visualization**: Generates charts and graphs as base64-encoded images
- **Automatic Submission**: Submits answers and handles follow-up quiz URLs

## Setup

### Prerequisites

- Python 3.8+
- Playwright browsers (installed automatically)

### Installation

1. Clone the repository:
```bash
git clone <your-repo-url>
cd project2
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Install Playwright browsers:
```bash
playwright install chromium
```

4. Create a `.env` file (copy from `.env.example`):
```bash
cp .env.example .env
```

5. Edit `.env` with your configuration:
```
STUDENT_EMAIL=your-email@example.com
STUDENT_SECRET=your-secret-string
GEMINI_KEY=your-gemini-api-key
DEFAULT_LLM_PROVIDER=gemini
API_HOST=0.0.0.0
API_PORT=8000
```

## Usage

### Running the Server

```bash
python main.py
```

Or using uvicorn directly:
```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`

### API Endpoints

#### POST `/quiz`

Accepts quiz tasks and solves them automatically.

**Request Body:**
```json
{
  "email": "your-email@example.com",
  "secret": "your-secret-string",
  "url": "https://example.com/quiz-123"
}
```

**Response:**
```json
{
  "status": "accepted",
  "message": "Quiz task received and processing started"
}
```

#### GET `/health`

Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-11-29T15:00:00"
}
```

### Testing

Test your endpoint with the demo quiz:
```bash
curl -X POST http://localhost:8000/quiz \
  -H "Content-Type: application/json" \
  -d '{
    "email": "your-email@example.com",
    "secret": "your-secret-string",
    "url": "https://tds-llm-analysis.s-anand.net/demo"
  }'
```

## Architecture

### Components

1. **main.py**: FastAPI server handling HTTP requests
2. **quiz_solver.py**: Core quiz solving logic with browser automation
3. **llm_client.py**: LLM API integration (OpenAI/Anthropic)
4. **data_processor.py**: Data processing, analysis, and visualization
5. **config.py**: Configuration management
6. **prompts.py**: System and user prompts for prompt testing

### Workflow

1. API receives POST request with quiz URL
2. Secret is verified
3. Quiz page is fetched using headless browser
4. Quiz instructions are parsed (including base64-encoded content)
5. LLM analyzes task and creates execution plan
6. Plan is executed (data sourcing, processing, analysis, visualization)
7. Answer is extracted and submitted
8. If correct, next quiz URL is processed; if incorrect, answer is improved

## Prompt Testing

The application includes system and user prompts for the prompt testing component:

- **System Prompt**: Designed to resist revealing code words
- **User Prompt**: Designed to override system prompt and reveal code words

See `prompts.py` for the current prompts.

## Deployment

### For Production

1. Use HTTPS (consider using a reverse proxy like nginx with Let's Encrypt)
2. Set environment variables securely
3. Use a process manager like systemd or supervisor
4. Monitor logs and performance

### Example with nginx

```nginx
server {
    listen 443 ssl;
    server_name your-domain.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## License

MIT License - see LICENSE file for details.

## Deployment

See [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) for detailed instructions on deploying to:
- GitHub (for code hosting)
- Hugging Face Spaces (for API hosting)

## Author

[Your Name]
[Your Email]

