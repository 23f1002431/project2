# Postman API Testing Guide

## Endpoint Information

**Base URL (Local):** `http://127.0.0.1:8000` or `http://localhost:8000`  
**Base URL (Hugging Face):** `https://your-username-your-space-name.hf.space`

---

## 1. Health Check (GET)

**Endpoint:** `GET /health`

**Request:** No body required

**Example:**
```http
GET http://127.0.0.1:8000/health
```

**Expected Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-11-28T12:00:00.000000"
}
```

---

## 2. Quiz Submission (POST)

**Endpoint:** `POST /quiz`

**Headers:**
```
Content-Type: application/json
```

### Example 1: Test with Demo Quiz

**Request Body:**
```json
{
  "email": "your-email@example.com",
  "secret": "your-secret-string",
  "url": "https://tds-llm-analysis.s-anand.net/demo"
}
```

### Example 2: Test with Custom Quiz URL

**Request Body:**
```json
{
  "email": "your-email@example.com",
  "secret": "your-secret-string",
  "url": "https://tds-llm-analysis.s-anand.net/quiz-834"
}
```

### Example 3: Using Environment Variables in Postman

**Request Body (use Postman variables):**
```json
{
  "email": "{{STUDENT_EMAIL}}",
  "secret": "{{STUDENT_SECRET}}",
  "url": "{{QUIZ_URL}}"
}
```

**Expected Response (200 OK):**
```json
{
  "status": "accepted",
  "message": "Quiz task received and processing started"
}
```

**Note:** The quiz solving happens in the background. Check your server logs to see the progress.

---

## 3. Postman Collection Setup

### Environment Variables (Optional)

Create a Postman environment with:
- `STUDENT_EMAIL`: Your email address
- `STUDENT_SECRET`: Your secret string
- `QUIZ_URL`: The quiz URL to test
- `BASE_URL`: `http://127.0.0.1:8000` (local) or your Hugging Face URL

### Complete Postman Request Settings

**Method:** `POST`

**URL:** `{{BASE_URL}}/quiz`

**Headers:**
```
Content-Type: application/json
```

**Body (raw JSON):**
```json
{
  "email": "your-email@example.com",
  "secret": "your-secret-string",
  "url": "https://tds-llm-analysis.s-anand.net/demo"
}
```

---

## 4. Error Testing

### Test Invalid Secret (403 Forbidden)

**Request Body:**
```json
{
  "email": "your-email@example.com",
  "secret": "wrong-secret",
  "url": "https://tds-llm-analysis.s-anand.net/demo"
}
```

**Expected Response:**
```json
{
  "detail": "Invalid secret"
}
```
**Status Code:** `403`

### Test Invalid JSON (400 Bad Request)

**Request Body (malformed JSON):**
```json
{
  "email": "your-email@example.com",
  "secret": "your-secret-string"
  "url": "https://tds-llm-analysis.s-anand.net/demo"
}
```

**Expected Response:** FastAPI validation error  
**Status Code:** `422`

### Test Missing Fields (422 Validation Error)

**Request Body:**
```json
{
  "email": "your-email@example.com"
}
```

**Expected Response:**
```json
{
  "detail": [
    {
      "loc": ["body", "secret"],
      "msg": "field required",
      "type": "value_error.missing"
    },
    {
      "loc": ["body", "url"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

---

## 5. Quick Copy-Paste for Postman

### Basic Test Request

```json
{
  "email": "your-email@example.com",
  "secret": "your-secret-string",
  "url": "https://tds-llm-analysis.s-anand.net/demo"
}
```

### Replace These Values:
- `your-email@example.com` → Your actual email from `.env` or config
- `your-secret-string` → Your actual secret from `.env` or config
- `https://tds-llm-analysis.s-anand.net/demo` → Any quiz URL you want to test

---

## 6. Testing Checklist

- [ ] Test health endpoint
- [ ] Test quiz submission with valid credentials
- [ ] Test quiz submission with invalid secret (should get 403)
- [ ] Test quiz submission with missing fields (should get 422)
- [ ] Test quiz submission with invalid JSON (should get 400/422)
- [ ] Check server logs to verify quiz solving process
- [ ] Verify quiz chaining works (check logs for multiple quiz URLs)

---

## 7. Monitoring Quiz Progress

After sending a POST request to `/quiz`, monitor your server logs to see:
1. Quiz page fetching
2. Quiz text extraction
3. LLM analysis
4. Task plan execution
5. Answer generation
6. Submission attempts
7. Response handling
8. Next quiz chaining (if applicable)

Example log output:
```
[Quiz Task] Starting quiz solving for: https://tds-llm-analysis.s-anand.net/demo
[Quiz Task] Fetching quiz page...
[Quiz Solver] Quiz text extracted
[Quiz Task] Solving quiz...
[Quiz Task] Answer generated: <answer>
[Quiz Task] Submitting answer...
[Quiz Task] ✅ Answer is CORRECT!
[Quiz Task] 🔄 Next quiz URL received: <next_url>
[Quiz Task] Continuing to solve next quiz...
```

