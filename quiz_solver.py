"""
Quiz Solver Module
Handles parsing quiz pages, solving tasks, and submitting answers.
"""
import re
import json
import base64
import asyncio
import logging
from typing import Dict, Any, Optional
from playwright.async_api import async_playwright, Page, Browser
import httpx
from bs4 import BeautifulSoup
import pandas as pd
import numpy as np
from PIL import Image
import io
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.graph_objects as go
import plotly.express as px

from llm_client import LLMClient
from data_processor import DataProcessor

logger = logging.getLogger(__name__)


class QuizSolver:
    """Main class for solving quiz tasks."""
    
    def __init__(self, llm_client: LLMClient, data_processor: DataProcessor):
        self.llm_client = llm_client
        self.data_processor = data_processor
        self.browser: Optional[Browser] = None
        self.playwright = None
        
    async def initialize_browser(self):
        """Initialize headless browser."""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=True)
        
    async def close_browser(self):
        """Close browser and cleanup."""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
    
    async def fetch_quiz_page(self, url: str) -> Dict[str, Any]:
        """
        Fetch and parse quiz page.
        Returns parsed quiz information.
        """
        if not self.browser:
            await self.initialize_browser()
            
        context = await self.browser.new_context()
        page = await context.new_page()
        
        try:
            # Navigate to quiz URL
            await page.goto(url, wait_until="networkidle", timeout=30000)
            
            # Wait for JavaScript to render
            await page.wait_for_timeout(2000)
            
            # Get page content
            content = await page.content()
            html = await page.inner_html("body")
            
            # Extract quiz instructions
            soup = BeautifulSoup(content, 'html.parser')
            
            # Look for base64 encoded content in script tags
            scripts = soup.find_all('script')
            quiz_text = ""
            submit_url = None
            
            for script in scripts:
                script_text = script.string or ""
                # Check for base64 encoded content
                if 'atob(' in script_text or 'btoa(' in script_text:
                    # Extract base64 string
                    base64_match = re.search(r'atob\(`([^`]+)`\)', script_text)
                    if base64_match:
                        try:
                            decoded = base64.b64decode(base64_match.group(1)).decode('utf-8')
                            quiz_text += decoded + "\n"
                        except:
                            pass
                
                # Look for submit URL
                url_match = re.search(r'https?://[^\s<>"\'\)]+/submit', script_text)
                if url_match:
                    submit_url = url_match.group(0)
            
            # Also check visible text on page
            visible_text = await page.evaluate("() => document.body.innerText")
            if visible_text:
                quiz_text += visible_text
            
            logger.info(f"[Quiz Solver] Quiz text extracted:")
            logger.info(f"  Length: {len(quiz_text)} characters")
            quiz_preview = quiz_text[:500] if len(quiz_text) > 500 else quiz_text
            logger.info(f"  Preview: {quiz_preview}...")
            if len(quiz_text) > 500:
                logger.info(f"  (Full text: {len(quiz_text)} characters)")
            
            # Extract submit URL from visible text if not found in scripts
            if not submit_url:
                url_match = re.search(r'https?://[^\s<>"\'\)]+/submit', visible_text or "")
                if url_match:
                    submit_url = url_match.group(0)
            
            # Take screenshot for visual analysis if needed
            screenshot = await page.screenshot(full_page=True)
            
            # Store context and page for later cleanup
            result = {
                "url": url,
                "html": html,
                "content": content,
                "quiz_text": quiz_text,
                "submit_url": submit_url,
                "screenshot": screenshot,
                "page": page,
                "context": context  # Store context for cleanup
            }
            
            return result
            
        except Exception as e:
            await context.close()
            raise Exception(f"Error fetching quiz page: {str(e)}")
    
    async def solve_quiz(self, quiz_info: Dict[str, Any]) -> Any:
        """
        Solve the quiz using LLM and data processing tools.
        Returns the answer in the appropriate format.
        """
        quiz_text = quiz_info["quiz_text"]
        page = quiz_info.get("page")
        context = quiz_info.get("context")
        
        try:
            logger.info(f"[Quiz Solver] Starting to solve quiz...")
            logger.info(f"[Quiz Solver] Quiz question received:")
            logger.info(f"  {quiz_text[:300]}..." if len(quiz_text) > 300 else f"  {quiz_text}")
            
            # Use LLM to understand the task and create a plan
            logger.info(f"[Quiz Solver] Sending quiz to LLM for analysis...")
            task_analysis = await self.llm_client.analyze_task(quiz_text)
            logger.info(f"[Quiz Solver] LLM analysis received:")
            logger.info(f"  Plan: {json.dumps(task_analysis, indent=2)}")
            
            # Execute the plan
            logger.info(f"[Quiz Solver] Executing task plan...")
            answer = await self.execute_task_plan(task_analysis, quiz_info)
            
            logger.info(f"[Quiz Solver] Final answer generated:")
            logger.info(f"  Type: {type(answer).__name__}")
            logger.info(f"  Value: {answer}")
            
            # Validation happens in execute_task_plan
            
            return answer
        finally:
            # Cleanup page and context
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
    
    async def execute_task_plan(self, task_plan: Dict[str, Any], quiz_info: Dict[str, Any]) -> Any:
        """
        Execute the task plan generated by LLM.
        Handles data sourcing, processing, analysis, and visualization.
        """
        steps = task_plan.get("steps", [])
        page = quiz_info.get("page")
        
        intermediate_results = {}
        
        for step in steps:
            step_type = step.get("type")
            step_description = step.get("description", "")
            
            if step_type == "download_file":
                # Download file from URL
                file_url = step.get("url")
                file_data = await self.data_processor.download_file(file_url)
                intermediate_results[step.get("name", "file")] = file_data
                
            elif step_type == "scrape_data":
                # Scrape data from page
                if page:
                    scraped_data = await self.scrape_page_data(page, step_description)
                    intermediate_results[step.get("name", "scraped")] = scraped_data
                    
            elif step_type == "api_call":
                # Make API call
                api_url = step.get("url")
                headers = step.get("headers", {})
                data = await self.data_processor.call_api(api_url, headers)
                intermediate_results[step.get("name", "api_data")] = data
                
            elif step_type == "process_data":
                # Process data (cleaning, transformation)
                input_data = intermediate_results.get(step.get("input"))
                processed = await self.data_processor.process_data(input_data, step_description)
                intermediate_results[step.get("name", "processed")] = processed
                
            elif step_type == "analyze_data":
                # Analyze data (filtering, aggregation, statistics)
                input_data = intermediate_results.get(step.get("input"))
                analysis_result = await self.data_processor.analyze_data(input_data, step_description)
                intermediate_results[step.get("name", "analysis")] = analysis_result
                
            elif step_type == "visualize":
                # Create visualization
                input_data = intermediate_results.get(step.get("input"))
                viz_result = await self.data_processor.create_visualization(input_data, step_description)
                intermediate_results[step.get("name", "visualization")] = viz_result
                
            elif step_type == "llm_reasoning":
                # Use LLM for complex reasoning
                context = {k: str(v)[:1000] for k, v in intermediate_results.items()}
                result = await self.llm_client.solve_step(step_description, context)
                intermediate_results[step.get("name", "llm_result")] = result
        
        # Final answer extraction
        try:
            final_answer = await self.llm_client.extract_answer(
                quiz_info["quiz_text"],
                intermediate_results
            )
        except Exception as e:
            logger.error(f"[Quiz Solver] ERROR: Failed to extract answer: {str(e)}")
            logger.error(f"[Quiz Solver] Intermediate results: {list(intermediate_results.keys())}")
            raise ValueError(f"Failed to generate answer: {str(e)}") from e
        
        # Validate answer is not empty
        if final_answer is None:
            logger.error(f"[Quiz Solver] ERROR: Final answer is None!")
            logger.error(f"[Quiz Solver] Intermediate results: {list(intermediate_results.keys())}")
            raise ValueError("Failed to generate answer: LLM returned None")
        
        if isinstance(final_answer, str) and not final_answer.strip():
            logger.error(f"[Quiz Solver] ERROR: Final answer is empty string!")
            logger.error(f"[Quiz Solver] Intermediate results: {list(intermediate_results.keys())}")
            raise ValueError("Failed to generate answer: LLM returned empty string")
        
        logger.info(f"[Quiz Solver] Answer validated successfully - not empty")
        return final_answer
    
    async def scrape_page_data(self, page: Page, description: str) -> Any:
        """Scrape specific data from page based on description."""
        # Use LLM to determine what to scrape
        scrape_instructions = await self.llm_client.get_scrape_instructions(description)
        
        # Execute scraping
        if scrape_instructions.get("type") == "table":
            # Extract table
            tables = await page.evaluate("""
                () => {
                    const tables = Array.from(document.querySelectorAll('table'));
                    return tables.map(table => {
                        const rows = Array.from(table.querySelectorAll('tr'));
                        return rows.map(row => {
                            const cells = Array.from(row.querySelectorAll('td, th'));
                            return cells.map(cell => cell.innerText.trim());
                        });
                    });
                }
            """)
            return tables
        elif scrape_instructions.get("type") == "text":
            # Extract specific text elements
            selector = scrape_instructions.get("selector", "body")
            text = await page.evaluate(f"""
                () => {{
                    const element = document.querySelector('{selector}');
                    return element ? element.innerText : '';
                }}
            """)
            return text
        else:
            # Generic content extraction
            content = await page.content()
            return content
    
    async def submit_answer(
        self, 
        submit_url: str, 
        email: str, 
        secret: str, 
        quiz_url: str, 
        answer: Any
    ) -> Dict[str, Any]:
        """
        Submit answer to the quiz endpoint.
        Returns the response from the server.
        """
        # Validate answer before submission
        if answer is None:
            logger.error(f"[Submit] ERROR: Cannot submit None answer")
            raise ValueError("Answer cannot be None")
        
        if isinstance(answer, str) and not answer.strip():
            logger.error(f"[Submit] ERROR: Cannot submit empty string answer")
            raise ValueError("Answer cannot be empty")
        
        payload = {
            "email": email,
            "secret": secret,
            "url": quiz_url,
            "answer": answer
        }
        
        logger.info(f"[Submit] Preparing submission:")
        logger.info(f"  Submit URL: {submit_url}")
        logger.info(f"  Answer type: {type(answer).__name__}")
        logger.info(f"  Answer value: {answer}")
        logger.info(f"  Payload: {json.dumps(payload, default=str)}")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(submit_url, json=payload)
            logger.info(f"[Submit] HTTP Status: {response.status_code}")
            response_data = response.json()
            logger.info(f"[Submit] Response: {json.dumps(response_data, default=str)}")
            return response_data


