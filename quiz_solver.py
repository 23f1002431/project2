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
from urllib.parse import urlparse
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
from code_executor import CodeExecutor

logger = logging.getLogger(__name__)


class QuizSolver:
    """Main class for solving quiz tasks."""
    
    def __init__(self, llm_client: LLMClient, data_processor: DataProcessor):
        self.llm_client = llm_client
        self.data_processor = data_processor
        self.code_executor = CodeExecutor()
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
            
            # Enhanced extraction: base64, tables, audio, media
            scripts = soup.find_all('script')
            quiz_text = ""
            extracted_media = {}
            
            # Extract base64 encoded content from scripts
            for script in scripts:
                script_text = script.string or ""
                # Check for base64 encoded content (multiple patterns)
                base64_patterns = [
                    r'atob\(["\']([^"\']+)["\']\)',
                    r'atob\(`([^`]+)`\)',
                    r'btoa\(["\']([^"\']+)["\']\)',
                    r'["\']([A-Za-z0-9+/=]{50,})["\']',  # Standalone base64 strings
                ]
                
                for pattern in base64_patterns:
                    matches = re.finditer(pattern, script_text)
                    for match in matches:
                        try:
                            base64_str = match.group(1)
                            # Try to decode as text
                            decoded = base64.b64decode(base64_str).decode('utf-8', errors='ignore')
                            quiz_text += decoded + "\n"
                        except:
                            # Might be binary data (audio, image, etc.)
                            try:
                                decoded_bytes = base64.b64decode(base64_str)
                                # Detect media type
                                if decoded_bytes.startswith(b'\xff\xfb') or decoded_bytes.startswith(b'ID3'):
                                    extracted_media[f'audio_{len(extracted_media)}'] = {
                                        'type': 'audio',
                                        'data': base64_str,
                                        'bytes': decoded_bytes[:100]  # Sample only
                                    }
                            except:
                                pass
            
            # Extract embedded base64 from data URIs (images, audio, etc.)
            data_uri_pattern = r'data:([^;]+);base64,([A-Za-z0-9+/=]+)'
            data_uris = re.finditer(data_uri_pattern, content)
            for match in data_uris:
                media_type = match.group(1)
                base64_data = match.group(2)
                if 'audio' in media_type:
                    extracted_media[f'audio_data_{len(extracted_media)}'] = {
                        'type': 'audio',
                        'mime': media_type,
                        'data': base64_data
                    }
                elif 'image' in media_type:
                    extracted_media[f'image_data_{len(extracted_media)}'] = {
                        'type': 'image',
                        'mime': media_type,
                        'data': base64_data
                    }
            
            # Extract audio elements
            audio_elements = await page.query_selector_all('audio')
            for i, audio in enumerate(audio_elements):
                src = await audio.get_attribute('src')
                if src:
                    extracted_media[f'audio_src_{i}'] = {
                        'type': 'audio_source',
                        'url': src
                    }
            
            # Extract video elements
            video_elements = await page.query_selector_all('video')
            for i, video in enumerate(video_elements):
                src = await video.get_attribute('src')
                if src:
                    extracted_media[f'video_src_{i}'] = {
                        'type': 'video_source',
                        'url': src
                    }
            
            # Extract embedded tables using JavaScript
            tables_data = await page.evaluate("""
                () => {
                    const tables = Array.from(document.querySelectorAll('table'));
                    return tables.map((table, idx) => {
                        const rows = Array.from(table.querySelectorAll('tr'));
                        const data = rows.map(row => {
                            const cells = Array.from(row.querySelectorAll('td, th'));
                            return cells.map(cell => cell.innerText.trim());
                        });
                        return {
                            index: idx,
                            data: data,
                            html: table.outerHTML
                        };
                    });
                }
            """)
            
            # Extract visible text
            visible_text = await page.evaluate("() => document.body.innerText")
            if visible_text:
                quiz_text += visible_text
            
            # Add table data to quiz text if found
            if tables_data:
                quiz_text += "\n\n=== EXTRACTED TABLES ===\n"
                for table_info in tables_data:
                    quiz_text += f"\nTable {table_info['index']}:\n"
                    for row in table_info['data']:
                        quiz_text += " | ".join(str(cell) for cell in row) + "\n"
            
            # Store extracted media in quiz_info
            if extracted_media:
                logger.info(f"[Quiz Solver] Extracted {len(extracted_media)} media items")
            
            logger.info(f"[Quiz Solver] Quiz text extracted:")
            logger.info(f"  Length: {len(quiz_text)} characters")
            quiz_preview = quiz_text[:500] if len(quiz_text) > 500 else quiz_text
            logger.info(f"  Preview: {quiz_preview}...")
            if len(quiz_text) > 500:
                logger.info(f"  (Full text: {len(quiz_text)} characters)")
            
            # Extract submit URL using improved logic
            submit_url = None
            
            # Try to find full URL first
            possible_urls = re.findall(r'https?://[^\s"]+', quiz_text)
            for u in possible_urls:
                if "submit" in u:
                    submit_url = u
                    logger.info(f"[Quiz Solver] Found submit URL in quiz text: {submit_url}")
                    break
            
            # If not found, check for relative submit path
            if not submit_url and "/submit" in quiz_text:
                parsed = urlparse(url)
                base_url = f"{parsed.scheme}://{parsed.netloc}"
                submit_url = base_url + "/submit"
                logger.info(f"[Quiz Solver] Using inferred submit URL: {submit_url}")
            
            if not submit_url:
                raise RuntimeError(f"No submit URL found in quiz text for {url}")
            
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
                "context": context,  # Store context for cleanup
                "extracted_media": extracted_media,
                "tables": tables_data if tables_data else []
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
                # Make API call (GET or POST)
                api_url = step.get("url")
                headers = step.get("headers", {})
                
                # Determine method: check step JSON first, then infer from description
                method = step.get("method", "").upper()
                if not method:
                    # Infer method from description
                    desc_lower = step_description.lower()
                    if "post" in desc_lower and "get" not in desc_lower:
                        method = "POST"
                    elif "get" in desc_lower:
                        method = "GET"
                    else:
                        method = "GET"  # Default
                
                post_data = step.get("data")  # For form data
                post_json = step.get("json")  # For JSON data
                
                # If POST but no JSON/data provided, try to extract from quiz text
                if method == "POST" and not post_json and not post_data:
                    quiz_text = quiz_info.get("quiz_text", "")
                    # Try to extract JSON from quiz text - look for JSON objects
                    # Pattern to match JSON objects (handles nested objects)
                    json_patterns = [
                        r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}',  # Simple nested JSON
                        r'\{.*?"email".*?\}',  # JSON with email field
                        r'\{.*?"answer".*?\}',  # JSON with answer field
                    ]
                    for pattern in json_patterns:
                        json_match = re.search(pattern, quiz_text, re.DOTALL)
                        if json_match:
                            try:
                                extracted_json_str = json_match.group(0)
                                # Clean up common issues
                                extracted_json_str = extracted_json_str.strip()
                                # Remove markdown code blocks if present
                                if extracted_json_str.startswith('```'):
                                    extracted_json_str = extracted_json_str.split('```')[1]
                                    if extracted_json_str.startswith('json'):
                                        extracted_json_str = extracted_json_str[4:]
                                extracted_json_str = extracted_json_str.strip()
                                
                                extracted_json = json.loads(extracted_json_str)
                                # Check if it has the structure we expect (email, secret, url, answer)
                                if isinstance(extracted_json, dict) and ("email" in extracted_json or "answer" in extracted_json):
                                    # Use actual values from quiz_info if available
                                    if "email" in extracted_json and extracted_json["email"] == "your email":
                                        # This is a template, don't use it
                                        continue
                                    post_json = extracted_json
                                    logger.info(f"[Quiz Solver] Extracted JSON payload from quiz text: {post_json}")
                                    break
                            except json.JSONDecodeError:
                                continue
                            except Exception as e:
                                logger.warning(f"[Quiz Solver] Failed to parse extracted JSON: {e}")
                                continue
                
                logger.info(f"[Quiz Solver] Making {method} request to {api_url}")
                if method == "POST":
                    logger.info(f"[Quiz Solver] POST payload: {post_json or post_data or 'None'}")
                
                data = await self.data_processor.call_api(
                    api_url, 
                    headers=headers,
                    method=method,
                    data=post_data,
                    json_data=post_json
                )
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
            
            elif step_type == "execute_code":
                # Execute Python code dynamically
                code = step.get("code", "")
                if not code:
                    # If no code provided, try to generate it from description using LLM
                    logger.info(f"[Quiz Solver] Generating code from description: {step_description}")
                    code = await self.llm_client.generate_code(step_description, intermediate_results)
                
                if code:
                    execution_result = await self.code_executor.execute_code(code)
                    if execution_result.get("error"):
                        logger.error(f"[Quiz Solver] Code execution error: {execution_result['error']}")
                        raise ValueError(f"Code execution failed: {execution_result['error']}")
                    
                    # Use result or plot as the output
                    if execution_result.get("plot"):
                        intermediate_results[step.get("name", "code_plot")] = execution_result["plot"]
                    elif execution_result.get("result") is not None:
                        intermediate_results[step.get("name", "code_result")] = execution_result["result"]
                    else:
                        intermediate_results[step.get("name", "code_output")] = execution_result.get("output", "")
                else:
                    logger.warning(f"[Quiz Solver] No code provided for execute_code step")
        
        # Final answer extraction with full context
        try:
            logger.info(f"[Quiz Solver] Extracting final answer from {len(intermediate_results)} intermediate results...")
            logger.info(f"[Quiz Solver] Intermediate result keys: {list(intermediate_results.keys())}")
            
            # Log summary of intermediate results for debugging
            for key, value in intermediate_results.items():
                if isinstance(value, (str, int, float, bool)):
                    logger.info(f"[Quiz Solver]   {key}: {value} (type: {type(value).__name__})")
                else:
                    logger.info(f"[Quiz Solver]   {key}: {type(value).__name__}")
            
            final_answer = await self.llm_client.extract_answer(
                quiz_info["quiz_text"],
                intermediate_results
            )
            logger.info(f"[Quiz Solver] ✅ Answer extracted successfully: {final_answer} (type: {type(final_answer).__name__})")
        except Exception as e:
            logger.error(f"[Quiz Solver] ERROR: Failed to extract answer: {str(e)}")
            logger.error(f"[Quiz Solver] Intermediate results keys: {list(intermediate_results.keys())}")
            # Log more details about intermediate results
            for key, value in intermediate_results.items():
                logger.error(f"[Quiz Solver]   {key}: {type(value).__name__} = {str(value)[:200]}")
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


