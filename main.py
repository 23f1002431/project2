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

# Health monitoring
class HealthMonitor:
    """Monitor system health and track background tasks."""
    
    def __init__(self):
        self.start_time = datetime.now()
        self.total_quizzes = 0
        self.successful_quizzes = 0
        self.failed_quizzes = 0
        self.active_tasks = 0
        self.task_history = []
    
    def record_quiz_start(self, quiz_url: str):
        """Record that a quiz task has started."""
        self.total_quizzes += 1
        self.active_tasks += 1
    
    def record_quiz_complete(self, quiz_url: str, success: bool):
        """Record that a quiz task has completed."""
        self.active_tasks = max(0, self.active_tasks - 1)
        if success:
            self.successful_quizzes += 1
        else:
            self.failed_quizzes += 1
        
        self.task_history.append({
            "url": quiz_url,
            "success": success,
            "timestamp": datetime.now().isoformat()
        })
        # Keep only last 100 entries
        if len(self.task_history) > 100:
            self.task_history = self.task_history[-100:]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current health statistics."""
        uptime = (datetime.now() - self.start_time).total_seconds()
        return {
            "uptime_seconds": uptime,
            "total_quizzes": self.total_quizzes,
            "successful_quizzes": self.successful_quizzes,
            "failed_quizzes": self.failed_quizzes,
            "active_tasks": self.active_tasks,
            "success_rate": (self.successful_quizzes / self.total_quizzes * 100) if self.total_quizzes > 0 else 0
        }

health_monitor = HealthMonitor()


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
    
    health_monitor.record_quiz_start(quiz_url)
    success = False
    
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
            # Cleanup page/context before returning
            page = quiz_info.get("page")
            context = quiz_info.get("context")
            if page:
                try:
                    await page.close()
                except:
                    pass
            if context:
                try:
                    await context.close()
                except:
                    pass
            return {
                "status": "error",
                "message": "Could not find submit URL in quiz page"
            }
        
        submit_url = quiz_info["submit_url"]
        logger.info(f"[Quiz Task] Submit URL found: {submit_url}")
        
        # Solve quiz (this will clean up page/context after solving)
        logger.info(f"[Quiz Task] Solving quiz...")
        try:
            answer = await quiz_solver.solve_quiz(quiz_info)
            logger.info(f"[Quiz Task] ✅ Answer generated: {answer} (type: {type(answer).__name__})")
        except Exception as e:
            logger.error(f"[Quiz Task] ERROR: Failed to solve quiz: {str(e)}", exc_info=True)
            # Cleanup on error
            page = quiz_info.get("page")
            context = quiz_info.get("context")
            if page:
                try:
                    await page.close()
                except:
                    pass
            if context:
                try:
                    await context.close()
                except:
                    pass
            raise
        
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
                logger.info(f"[Quiz Task] ✅ Answer is CORRECT!")
                # Answer is correct - check for next quiz
                next_url = response.get("url")
                if next_url and next_url.strip():
                    logger.info(f"[Quiz Task] 🔄 Next quiz URL received: {next_url}")
                    logger.info(f"[Quiz Task] Continuing to solve next quiz...")
                    # Continue to next quiz - recursively solve
                    result = await solve_quiz_task(email, secret, next_url, start_time)
                    # Merge results if needed
                    return result
                else:
                    logger.info(f"[Quiz Task] ✅ All quizzes completed successfully!")
                    success = True
                    health_monitor.record_quiz_complete(quiz_url, True)
                    # Quiz complete - no more URLs
                    return {
                        "status": "success",
                        "correct": True,
                        "url": None,
                        "reason": response.get("reason", "All quizzes completed successfully")
                    }
            else:
                logger.warning(f"[Quiz Task] ❌ Answer is INCORRECT. Reason: {response.get('reason')}")
                # Answer is wrong
                next_url = response.get("url")
                
                # If a new URL is provided, we can either:
                # 1. Continue to that URL (skip retry for current quiz)
                # 2. Or retry current quiz and ignore the new URL
                # Based on requirements: "you may receive the next url to proceed to. If so, you can choose to skip to that URL instead of re-submitting to the current one."
                if next_url and next_url.strip():
                    logger.info(f"[Quiz Task] 🔄 New URL provided despite incorrect answer, moving to: {next_url}")
                    logger.info(f"[Quiz Task] Skipping retry and continuing to next quiz...")
                    # Continue to next quiz instead of retrying
                    return await solve_quiz_task(email, secret, next_url, start_time)
                else:
                    # No new URL - try to improve and resubmit
                    if attempt < max_attempts - 1:
                        logger.info(f"[Quiz Task] 🔄 Improving answer based on feedback (attempt {attempt + 1}/{max_attempts})...")
                        logger.info(f"[Quiz Task] Feedback: {response.get('reason', 'No feedback provided')}")
                        # Use feedback to improve
                        reason = response.get("reason", "")
                        improved_answer = await improve_answer(quiz_info, answer, reason)
                        logger.info(f"[Quiz Task] Improved answer: {improved_answer} (was: {answer})")
                        answer = improved_answer
                        # Continue loop to retry submission with improved answer
                        continue
                    else:
                        logger.error(f"[Quiz Task] ❌ Failed after {max_attempts} attempts for: {quiz_url}")
                        health_monitor.record_quiz_complete(quiz_url, False)
                        return {
                            "status": "incorrect",
                            "correct": False,
                            "reason": response.get("reason", "Failed after multiple attempts"),
                            "url": quiz_url
                        }
        
        logger.error(f"[Quiz Task] Exhausted all attempts for: {quiz_url}")
        health_monitor.record_quiz_complete(quiz_url, False)
        return {
            "status": "error",
            "message": "Failed to solve quiz after multiple attempts"
        }
        
    except Exception as e:
        logger.error(f"[Quiz Task] Exception while solving quiz: {str(e)}", exc_info=True)
        health_monitor.record_quiz_complete(quiz_url, False)
        return {
            "status": "error",
            "message": f"Error solving quiz: {str(e)}"
        }
    finally:
        # Ensure we record completion even if task fails unexpectedly
        if not success:
            health_monitor.record_quiz_complete(quiz_url, False)


async def improve_answer(
    quiz_info: Dict[str, Any], 
    current_answer: Any, 
    feedback: str
) -> Any:
    """Use LLM to improve answer based on feedback."""
    quiz_text = quiz_info.get('quiz_text', '')
    
    logger.info(f"[Improve Answer] Analyzing feedback to improve answer...")
    logger.info(f"[Improve Answer] Current answer: {current_answer}")
    logger.info(f"[Improve Answer] Feedback: {feedback}")
    
    prompt = f"""The previous answer was incorrect. Analyze the feedback and quiz task carefully to provide a correct answer.

Quiz Task:
{quiz_text}

Previous Answer: {current_answer}
Feedback: {feedback}

INSTRUCTIONS:
1. Carefully review the quiz task to understand what is actually being asked
2. Analyze why the previous answer was incorrect based on the feedback
3. Re-examine the problem and identify the correct approach
4. Provide a new, improved answer that addresses the feedback
5. Ensure your answer is accurate and matches the expected format

CRITICAL: Return ONLY the improved answer itself, nothing else. No explanations, no prefix, just the answer.

Improved Answer:"""
    
    improved = await llm_client._call_llm(prompt)
    parsed = llm_client._parse_response(improved)
    
    logger.info(f"[Improve Answer] Improved answer: {parsed} (type: {type(parsed).__name__})")
    return parsed


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
        
        # Store task info
        task_id = f"{quiz_request.url}_{datetime.now().timestamp()}"
        active_sessions[task_id] = {
            "url": quiz_request.url,
            "started_at": datetime.now().isoformat(),
            "status": "processing"
        }
        
        # Use asyncio.create_task to run in background (fire and forget)
        async def task_with_cleanup():
            try:
                result = await solve_quiz_task(
                    quiz_request.email,
                    quiz_request.secret,
                    quiz_request.url
                )
                active_sessions[task_id]["status"] = result.get("status", "completed")
                active_sessions[task_id]["completed_at"] = datetime.now().isoformat()
                active_sessions[task_id]["result"] = result
            except Exception as e:
                logger.error(f"Error in background task: {e}", exc_info=True)
                active_sessions[task_id]["status"] = "error"
                active_sessions[task_id]["error"] = str(e)
                active_sessions[task_id]["completed_at"] = datetime.now().isoformat()
            finally:
                # Cleanup old sessions (keep last 50)
                if len(active_sessions) > 50:
                    oldest_key = min(active_sessions.keys(), key=lambda k: active_sessions[k].get("started_at", ""))
                    del active_sessions[oldest_key]
        
        task = asyncio.create_task(task_with_cleanup())
        logger.info(f"Background task created for quiz: {quiz_request.url} (task_id: {task_id})")
        
        # Return immediate response
        return JSONResponse(
            status_code=200,
            content={
                "status": "accepted",
                "message": "Quiz task received and processing started",
                "task_id": task_id
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error handling quiz request: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.get("/health")
async def health_check():
    """Health check endpoint with detailed statistics."""
    logger.debug("Health check requested")
    stats = health_monitor.get_stats()
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "uptime_seconds": stats["uptime_seconds"],
        "total_quizzes": stats["total_quizzes"],
        "successful_quizzes": stats["successful_quizzes"],
        "failed_quizzes": stats["failed_quizzes"],
        "active_tasks": stats["active_tasks"],
        "success_rate": round(stats["success_rate"], 2)
    }


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

