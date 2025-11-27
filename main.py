"""
Main FastAPI server for quiz solver application.
"""
import asyncio
import sys
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import config
from quiz_solver import QuizSolver
from llm_client import LLMClient
from data_processor import DataProcessor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Ensure Windows event loop supports subprocesses for Playwright
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())


app = FastAPI(title="Quiz Solver API", version="1.0.0")

# Initialize components
llm_client = LLMClient()
data_processor = DataProcessor()
quiz_solver = QuizSolver(llm_client, data_processor)

# Track active quiz sessions
active_sessions: Dict[str, Dict[str, Any]] = {}


class QuizRequest(BaseModel):
    """Request model for quiz endpoint."""
    email: str = Field(..., description="Student email address", example="your-email@example.com")
    secret: str = Field(..., description="Secret string for verification", example="your-secret-string")
    url: str = Field(..., description="Quiz URL to solve", example="https://tds-llm-analysis.s-anand.net/demo")
    
    class Config:
        extra = "allow"


class QuizResponse(BaseModel):
    """Response model for quiz endpoint."""
    status: str
    message: str
    correct: Optional[bool] = None
    url: Optional[str] = None
    reason: Optional[str] = None


async def verify_secret(secret: str) -> bool:
    """Verify if secret matches configured secret."""
    return secret == config.STUDENT_SECRET


async def solve_quiz_task(email: str, secret: str, quiz_url: str, start_time: datetime = None) -> Dict[str, Any]:
    """
    Main function to solve a quiz task.
    Handles fetching, solving, and submitting answers.
    """
    if start_time is None:
        start_time = datetime.now()
    timeout = timedelta(seconds=config.QUIZ_TIMEOUT)
    
    try:
        logger.info(f"[Quiz Task] Starting quiz solving for: {quiz_url}")
        
        # Check timeout
        if datetime.now() - start_time > timeout:
            logger.error(f"[Quiz Task] Timeout exceeded for: {quiz_url}")
            return {
                "status": "timeout",
                "message": "Quiz solving exceeded time limit"
            }
        
        # Fetch quiz page
        logger.info(f"[Quiz Task] Fetching quiz page: {quiz_url}")
        quiz_info = await quiz_solver.fetch_quiz_page(quiz_url)
        
        # Log extracted quiz information
        quiz_text = quiz_info.get("quiz_text", "")
        logger.info(f"[Quiz Task] Quiz page fetched successfully")
        logger.info(f"[Quiz Task] Quiz text extracted:")
        logger.info(f"  Length: {len(quiz_text)} characters")
        quiz_preview = quiz_text[:400] if len(quiz_text) > 400 else quiz_text
        logger.info(f"  Preview: {quiz_preview}...")
        if len(quiz_text) > 400:
            logger.info(f"  (Full text available, {len(quiz_text)} characters total)")
        
        if not quiz_info.get("submit_url"):
            logger.error(f"[Quiz Task] No submit URL found for: {quiz_url}")
            return {
                "status": "error",
                "message": "Could not find submit URL in quiz page"
            }
        
        submit_url = quiz_info["submit_url"]
        logger.info(f"[Quiz Task] Submit URL found: {submit_url}")
        
        # Solve quiz
        logger.info(f"[Quiz Task] Solving quiz...")
        answer = await quiz_solver.solve_quiz(quiz_info)
        logger.info(f"[Quiz Task] Answer generated: {answer}")
        
        # Submit answer
        max_attempts = 3
        for attempt in range(max_attempts):
            if datetime.now() - start_time > timeout:
                logger.error(f"[Quiz Task] Timeout during submission attempt {attempt + 1}")
                return {
                    "status": "timeout",
                    "message": "Quiz solving exceeded time limit"
                }
            
            # Validate answer before attempting submission
            if answer is None or (isinstance(answer, str) and not answer.strip()):
                logger.error(f"[Quiz Task] ERROR: Cannot submit empty answer (attempt {attempt + 1})")
                logger.error(f"[Quiz Task] Answer value: {repr(answer)}")
                # Try to improve/generate answer again
                if attempt < max_attempts - 1:
                    logger.info(f"[Quiz Task] Attempting to regenerate answer...")
                    # Re-analyze and solve
                    task_analysis = await quiz_solver.llm_client.analyze_task(quiz_info.get("quiz_text", ""))
                    answer = await quiz_solver.execute_task_plan(task_analysis, quiz_info)
                    logger.info(f"[Quiz Task] Regenerated answer: {answer}")
                    continue
                else:
                    return {
                        "status": "error",
                        "message": "Failed to generate answer: LLM returned empty response after multiple attempts"
                    }
            
            logger.info(f"[Quiz Task] Submitting answer (attempt {attempt + 1}/{max_attempts})...")
            logger.info(f"[Quiz Task] Answer being submitted: {answer} (type: {type(answer).__name__})")
            try:
                response = await quiz_solver.submit_answer(
                    submit_url, email, secret, quiz_url, answer
                )
                logger.info(f"[Quiz Task] Submission response received:")
                logger.info(f"  Correct: {response.get('correct', 'N/A')}")
                logger.info(f"  Reason: {response.get('reason', 'N/A')}")
                logger.info(f"  Next URL: {response.get('url', 'None (quiz complete)')}")
                logger.info(f"  Full response: {response}")
            except Exception as e:
                logger.error(f"[Quiz Task] Submission error (attempt {attempt + 1}): {str(e)}", exc_info=True)
                # If submission fails, try again
                if attempt < max_attempts - 1:
                    continue
                else:
                    return {
                        "status": "error",
                        "message": f"Failed to submit answer: {str(e)}"
                    }
            
            if response.get("correct"):
                logger.info(f"[Quiz Task] Answer is CORRECT!")
                # Answer is correct
                next_url = response.get("url")
                if next_url:
                    logger.info(f"[Quiz Task] Moving to next quiz: {next_url}")
                    # Continue to next quiz
                    return await solve_quiz_task(email, secret, next_url, start_time)
                else:
                    logger.info(f"[Quiz Task] Quiz completed successfully!")
                    # Quiz complete
                    return {
                        "status": "success",
                        "correct": True,
                        "url": None,
                        "reason": response.get("reason", "Quiz completed")
                    }
            else:
                logger.warning(f"[Quiz Task] Answer is INCORRECT. Reason: {response.get('reason')}")
                # Answer is wrong
                if response.get("url"):
                    logger.info(f"[Quiz Task] New URL provided, moving to: {response.get('url')}")
                    # New URL provided, solve that instead
                    next_url = response["url"]
                    return await solve_quiz_task(email, secret, next_url, start_time)
                else:
                    # Try to improve answer
                    if attempt < max_attempts - 1:
                        logger.info(f"[Quiz Task] Improving answer based on feedback...")
                        # Use feedback to improve
                        reason = response.get("reason", "")
                        answer = await improve_answer(quiz_info, answer, reason)
                    else:
                        logger.error(f"[Quiz Task] Failed after {max_attempts} attempts")
                        return {
                            "status": "incorrect",
                            "correct": False,
                            "reason": response.get("reason")
                        }
        
        logger.error(f"[Quiz Task] Exhausted all attempts for: {quiz_url}")
        return {
            "status": "error",
            "message": "Failed to solve quiz after multiple attempts"
        }
        
    except Exception as e:
        logger.error(f"[Quiz Task] Exception while solving quiz: {str(e)}", exc_info=True)
        return {
            "status": "error",
            "message": f"Error solving quiz: {str(e)}"
        }


async def improve_answer(
    quiz_info: Dict[str, Any], 
    current_answer: Any, 
    feedback: str
) -> Any:
    """Use LLM to improve answer based on feedback."""
    prompt = f"""The previous answer was incorrect. Feedback: {feedback}
    
Quiz task: {quiz_info.get('quiz_text', '')}
Previous answer: {current_answer}

Provide an improved answer."""
    
    improved = await llm_client.solve_step(prompt, {})
    return improved


@app.post("/quiz", response_model=QuizResponse)
async def handle_quiz(quiz_request: QuizRequest):
    """
    Main endpoint for receiving quiz tasks.
    
    Accepts a POST request with quiz task details and processes it asynchronously.
    
    - **email**: Student email address
    - **secret**: Secret string for verification
    - **url**: Quiz URL to solve
    """
    try:
        logger.info(f"Received quiz request for URL: {quiz_request.url}")
        
        # Verify secret
        if not await verify_secret(quiz_request.secret):
            logger.warning(f"Invalid secret provided for email: {quiz_request.email}")
            raise HTTPException(status_code=403, detail="Invalid secret")
        
        logger.info(f"Secret verified. Starting quiz solving for: {quiz_request.url}")
        
        # Verify email matches configured email (optional check)
        if quiz_request.email != config.STUDENT_EMAIL:
            logger.warning(f"Email mismatch: {quiz_request.email} vs {config.STUDENT_EMAIL}")
        
        # Use asyncio.create_task to run in background (fire and forget)
        task = asyncio.create_task(
            solve_quiz_task(
                quiz_request.email,
                quiz_request.secret,
                quiz_request.url
            )
        )
        logger.info(f"Background task created for quiz: {quiz_request.url}")
        
        # Return immediate response
        return JSONResponse(
            status_code=200,
            content={
                "status": "accepted",
                "message": "Quiz task received and processing started"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error handling quiz request: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    logger.debug("Health check requested")
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.post("/test-submit")
async def test_submit(request: Request):
    """
    Test endpoint to simulate quiz submission responses.
    Use this for testing your quiz solver locally.
    
    Accepts the same format as real quiz submissions.
    Returns test responses to verify your solver handles different scenarios.
    """
    try:
        body = await request.json()
        answer = body.get("answer")
        quiz_url = body.get("url", "")
        
        logger.info(f"[Test Submit] Received answer: {answer} for quiz: {quiz_url}")
        logger.info(f"[Test Submit] Answer type: {type(answer).__name__}")
        
        # Simple test: Check if answer is 4 (for "What is 2 + 2?")
        if answer == 4:
            logger.info("[Test Submit] Answer is CORRECT!")
            return {
                "correct": True,
                "url": None,  # No next quiz
                "reason": "Correct! The answer is 4."
            }
        else:
            logger.info(f"[Test Submit] Answer is INCORRECT. Expected 4, got {answer}")
            return {
                "correct": False,
                "url": None,
                "reason": f"Incorrect. You answered {answer}, but the correct answer is 4."
            }
    except Exception as e:
        logger.error(f"[Test Submit] Error: {str(e)}", exc_info=True)
        return {
            "correct": False,
            "reason": f"Error processing submission: {str(e)}"
        }


@app.on_event("startup")
async def startup_event():
    """Initialize browser on startup."""
    logger.info("Starting up Quiz Solver API...")
    try:
        await quiz_solver.initialize_browser()
        logger.info("Browser initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize browser: {str(e)}", exc_info=True)
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("Shutting down Quiz Solver API...")
    try:
        await quiz_solver.close_browser()
        logger.info("Browser closed successfully")
    except Exception as e:
        logger.error(f"Error closing browser: {str(e)}", exc_info=True)


if __name__ == "__main__":
    import uvicorn
    import os
    # Use PORT env variable (for Hugging Face Spaces) or fall back to config
    port = int(os.getenv("PORT", config.API_PORT))
    uvicorn.run(app, host=config.API_HOST, port=port)

