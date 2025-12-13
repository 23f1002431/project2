# Autonomous Quiz Solving System

An intelligent, production-ready system that autonomously solves complex quiz chains across multiple URLs using LLM-powered reasoning, advanced data processing, and dynamic code execution.

## Features

### ✅ Autonomous Quiz Solving
- **Quiz Chain Navigation**: Automatically follows quiz chains across multiple URLs
- **Answer Submission**: Submits answers and processes evaluator responses
- **Retry Logic**: Detects wrong answers, retries with improved solutions, and moves ahead
- **Multi-Step Chains**: Handles complex multi-step question chains seamlessly

### 🌐 Enhanced Scraping & Rendering
- **Playwright Chromium**: Uses Playwright Chromium for JavaScript-heavy pages
- **Advanced Extraction**: Extracts tables, text, scripts, and embedded base64 content
- **Media Handling**: Processes audio files, video elements, and media content
- **Dynamic Content**: Handles dynamic web content with full JavaScript rendering
- **Base64 Decoding**: Automatically decodes base64-encoded quiz instructions

### 📊 Comprehensive Data Processing
- **Multi-Format Support**: Processes CSV, PDF, JSON, HTML tables, and more
- **Numerical Operations**: Performs complex numerical and statistical operations
- **Data Cleansing**: Handles data cleaning, transformation, and normalization
- **Advanced Aggregation**: Supports filtering, sorting, grouping, and aggregation
- **Table Extraction**: Extracts and processes tables from HTML and PDFs

### 🎨 Visualization & Execution
- **Plot Generation**: Generates plots/images in base64 format (bar, line, scatter, histogram, pie, box, heatmap)
- **File Management**: Downloads and manages temporary files
- **Dynamic Code Execution**: Runs dynamically generated Python code safely
- **Sandboxed Environment**: Secure, restricted execution environment for code

### 🧠 LLM-Powered Intelligence
- **Google Gemini 2.5 Flash**: Uses Gemini 2.5 Flash for intelligent reasoning
- **Tool Selection**: Intelligently decides which tool to execute next
- **Action Planning**: Plans multi-step actions intelligently
- **Adaptive Learning**: Learns from evaluator responses to improve answers

### 🏭 Production Ready
- **Dockerized**: Fully containerized for fast deployment
- **Multi-Platform**: Works on Render, Railway, Hugging Face Spaces
- **Health Monitoring**: Comprehensive health monitoring with statistics
- **Background Tasks**: Efficient background task management
- **Performance Optimized**: Optimized for production performance

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
GEMINI_MODEL=gemini-2.5-flash
API_HOST=0.0.0.0
API_PORT=8000
LLM_MAX_TOKENS=2000
LLM_TEMPERATURE=0.3
LLM_REQUEST_TIMEOUT=60
QUIZ_TIMEOUT=180
REQUEST_TIMEOUT=30
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

Health check endpoint with detailed statistics.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-11-29T15:00:00",
  "uptime_seconds": 3600,
  "total_quizzes": 10,
  "successful_quizzes": 8,
  "failed_quizzes": 2,
  "active_tasks": 1,
  "success_rate": 80.0
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

1. **main.py**: FastAPI server with health monitoring and background task management
2. **quiz_solver.py**: Core quiz solving logic with enhanced browser automation
3. **llm_client.py**: LLM API integration (Google Gemini 2.5 Flash) with code generation
4. **data_processor.py**: Advanced data processing, analysis, and visualization
5. **code_executor.py**: Sandboxed Python code execution environment
6. **config.py**: Configuration management with environment variable support
7. **prompts.py**: System and user prompts for prompt testing

### Workflow

1. **API receives POST request** with quiz URL
2. **Secret verification** validates the request
3. **Quiz page fetched** using Playwright Chromium with full JS rendering
4. **Content extraction** parses quiz instructions, base64, tables, audio, media
5. **LLM analysis** uses Gemini 2.5 Flash to understand task and create execution plan
6. **Plan execution**:
   - Downloads files (CSV, PDF, JSON, etc.)
   - Scrapes web data
   - Makes API calls
   - Processes data (cleaning, transformation)
   - Analyzes data (filtering, aggregation, statistics)
   - Generates visualizations (plots as base64)
   - Executes dynamic Python code (sandboxed)
   - Uses LLM reasoning for complex steps
7. **Answer extraction** from intermediate results
8. **Answer submission** to quiz endpoint
9. **Response handling**:
   - If correct: Process next quiz URL (chain continuation)
   - If incorrect: Improve answer using feedback and retry
   - Track success/failure in health monitor

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

