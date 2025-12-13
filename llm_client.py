"""
LLM Client Module
Handles interactions with the configured LLM provider.
"""
import json
import re
import logging
from typing import Dict, Any, Optional
import httpx
import config
import pandas as pd

logger = logging.getLogger(__name__)


class LLMClient:
    """Client for interacting with LLM APIs."""
    
    def __init__(self, provider: str = None):
        self.provider = (provider or config.DEFAULT_LLM_PROVIDER).lower()
        self._default_system_prompt = (
            "You are a helpful assistant that solves data analysis tasks."
        )
    
    def _call_llm(self, prompt: str, system_prompt: str = None) -> str:
        """Make API call to configured LLM provider (synchronous wrapper)."""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        # If already in async context, use the async version
        if loop.is_running():
            # We're in an async context, need to handle differently
            # For now, use synchronous version
            return self._call_llm_sync(prompt, system_prompt)
        else:
            return loop.run_until_complete(self._call_llm_async(prompt, system_prompt))
    
    def _call_llm_sync(self, prompt: str, system_prompt: str = None) -> str:
        """Synchronous version for backward compatibility."""
        logger.debug(f"[LLM Client] Calling LLM with provider: {self.provider}")
        if self.provider == "gemini":
            return self._call_gemini(prompt, system_prompt)
        raise ValueError(f"Unsupported LLM provider: {self.provider}")
    
    async def _call_llm_async(self, prompt: str, system_prompt: str = None) -> str:
        """Async version."""
        return self._call_llm_sync(prompt, system_prompt)
    
    async def analyze_task(self, quiz_text: str) -> Dict[str, Any]:
        """
        Analyze quiz task and create a step-by-step plan.
        """
        logger.info(f"[LLM Client] Analyzing quiz task...")
        logger.info(f"[LLM Client] Quiz text sent to LLM:")
        logger.info(f"  {quiz_text[:300]}..." if len(quiz_text) > 300 else f"  {quiz_text}")
        
        prompt = f"""You are an expert data analyst. Analyze this quiz task carefully and create a detailed, step-by-step plan to solve it correctly.

Quiz Task:
{quiz_text}

INSTRUCTIONS:
1. Read the quiz task carefully and identify what is being asked
2. Determine what data sources you need (files, APIs, web scraping, etc.)
3. Plan the sequence of operations needed to solve it
4. Be specific about data processing, analysis, and calculations required
5. Ensure your plan will lead to the correct answer

Create a JSON plan with the following structure:
{{
    "steps": [
        {{
                    "type": "download_file|scrape_data|api_call|process_data|analyze_data|visualize|llm_reasoning|execute_code",
            "description": "detailed description of what to do in this step - be specific about operations",
            "name": "unique_name_for_result",
            "url": "if applicable",
            "headers": {{"if": "api_call"}},
            "method": "GET|POST (REQUIRED for api_call - use POST if description mentions POST, GET otherwise)",
            "data": {{"if": "POST request with form data"}},
            "json": {{"if": "POST request with JSON body - extract JSON from quiz text if mentioned"}},
            "input": "name_of_previous_step_result"
        }}
    ]
}}

IMPORTANT:
- For api_call steps: If the description mentions "POST" or "post", set "method": "POST"
- If the quiz text contains a JSON payload to send, extract it and include it in the "json" field
- Always include the "method" field for api_call steps
- For analyze_data steps: Be very specific about what calculations or aggregations to perform
- Break down complex tasks into smaller, clear steps
- Each step should build upon previous steps

Return only valid JSON, no other text."""
        
        logger.info(f"[LLM Client] Calling LLM API...")
        response = self._call_llm(prompt)
        logger.info(f"[LLM Client] LLM response received:")
        logger.info(f"  Response length: {len(response)} characters")
        logger.info(f"  Response preview: {response[:500]}..." if len(response) > 500 else f"  Response: {response}")
        
        # Extract JSON from response
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except:
                pass
        
        # Fallback plan
        return {
            "steps": [
                {
                    "type": "llm_reasoning",
                    "description": quiz_text,
                    "name": "answer"
                }
            ]
        }
    
    async def solve_step(self, description: str, context: Dict[str, Any] = None) -> Any:
        """Use LLM to solve a specific step."""
        logger.info(f"[LLM Client] Solving step: {description[:200]}...")
        
        context_str = ""
        if context:
            context_str = "\n\nContext:\n" + json.dumps(context, indent=2)
            logger.info(f"[LLM Client] Context provided: {len(str(context))} characters")
        
        prompt = f"""Solve this task step carefully and accurately:

{description}
{context_str}

INSTRUCTIONS:
1. Understand exactly what the step requires
2. Use the context information provided
3. Perform any calculations or operations needed
4. Return the result in the correct format

Return Guidelines:
- If the answer is a number, return ONLY the number (integer or float)
- If it's text, return the text string
- If it's a boolean, return true or false
- Be precise and accurate - double-check your calculations

Result:"""
        
        logger.info(f"[LLM Client] Sending prompt to LLM (length: {len(prompt)} chars)...")
        response = self._call_llm(prompt)
        logger.info(f"[LLM Client] LLM response: {response}")
        
        parsed = self._parse_response(response)
        logger.info(f"[LLM Client] Parsed answer: {parsed} (type: {type(parsed).__name__})")
        return parsed
    
    async def extract_answer(
        self, 
        quiz_text: str, 
        intermediate_results: Dict[str, Any]
    ) -> Any:
        """
        Extract final answer from intermediate results.
        """
        logger.info(f"[LLM Client] Extracting final answer from intermediate results...")
        logger.info(f"[LLM Client] Intermediate results: {list(intermediate_results.keys())}")
        
        import pandas as pd
        import numpy as np
        
        # Create detailed summary of intermediate results
        results_summary = {}
        results_details = {}
        
        for key, value in intermediate_results.items():
            if isinstance(value, (str, int, float, bool)):
                results_summary[key] = value
                results_details[key] = value
            elif isinstance(value, pd.DataFrame):
                results_summary[key] = f"DataFrame with shape {value.shape}"
                # Include actual data if small enough
                if value.shape[0] <= 100 and value.shape[1] <= 20:
                    results_details[key] = value.to_dict(orient='records')[:10]  # First 10 rows
                else:
                    # For larger DataFrames, include summary statistics and sample
                    summary_info = {
                        "shape": list(value.shape),
                        "columns": list(value.columns),
                        "sample": value.head(5).to_dict(orient='records') if not value.empty else []
                    }
                    # Add numeric column summaries
                    numeric_cols = value.select_dtypes(include=[np.number]).columns
                    if len(numeric_cols) > 0:
                        summary_info["numeric_summary"] = value[numeric_cols].describe().to_dict()
                    results_details[key] = summary_info
            elif isinstance(value, (list, dict)):
                results_summary[key] = f"{type(value).__name__} with {len(value)} items"
                # Include actual content if not too large
                if isinstance(value, dict) and len(str(value)) < 5000:
                    results_details[key] = value
                elif isinstance(value, list) and len(value) <= 20:
                    results_details[key] = value[:20]
                else:
                    results_details[key] = str(value)[:1000] + "..." if len(str(value)) > 1000 else value
            else:
                results_summary[key] = str(type(value).__name__)
                results_details[key] = str(value)[:500] if len(str(value)) > 500 else str(value)
        
        prompt = f"""You are an expert at solving data analysis problems. Based on the quiz task and intermediate results, extract the FINAL ANSWER.

Quiz Task:
{quiz_text}

Intermediate Results Summary:
{json.dumps(results_summary, indent=2)}

Detailed Intermediate Results:
{json.dumps(results_details, indent=2, default=str)}

INSTRUCTIONS:
1. Review the quiz task carefully to understand what answer is expected
2. Examine all intermediate results to find the relevant data
3. Perform any final calculations or aggregations needed
4. Extract the EXACT answer requested in the quiz task
5. Ensure your answer matches the expected format

Answer Format Guidelines:
- If the quiz asks for a NUMBER (sum, count, average, etc.), return ONLY the number as an integer or float
- If the quiz asks for TEXT (name, description, etc.), return the text string
- If the quiz asks for a BOOLEAN (true/false, yes/no), return true or false
- If the quiz asks for a JSON object, return valid JSON
- If the quiz asks for an image/visualization, provide details on how to generate it

CRITICAL: Return ONLY the answer itself, nothing else. No explanations, no prefix, no suffix. Just the answer.

Answer:"""
        
        logger.info(f"[LLM Client] Sending extraction prompt to LLM...")
        response = self._call_llm(prompt)
        logger.info(f"[LLM Client] LLM extraction response: {response}")
        
        parsed = self._parse_response(response)
        logger.info(f"[LLM Client] Final extracted answer: {parsed} (type: {type(parsed).__name__})")
        return parsed
    
    async def get_scrape_instructions(self, description: str) -> Dict[str, Any]:
        """Get instructions for what to scrape from a page."""
        prompt = f"""Given this task description, determine what data to scrape from a web page:
{description}

Return JSON with:
{{
    "type": "table|text|generic",
    "selector": "CSS selector if type is text"
}}"""
        
        response = self._call_llm(prompt)
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except:
                pass
        
        return {"type": "generic", "selector": "body"}
    
    async def generate_code(self, description: str, context: Dict[str, Any] = None) -> str:
        """Generate Python code based on description and context."""
        logger.info(f"[LLM Client] Generating code for: {description[:200]}...")
        
        context_str = ""
        if context:
            context_summary = {}
            for key, value in context.items():
                if isinstance(value, (str, int, float, bool)):
                    context_summary[key] = value
                elif isinstance(value, pd.DataFrame):
                    context_summary[key] = f"DataFrame with shape {value.shape}"
                else:
                    context_summary[key] = str(type(value).__name__)
            context_str = "\n\nAvailable Variables:\n" + json.dumps(context_summary, indent=2)
        
        prompt = f"""Generate Python code to solve this task:

{description}
{context_str}

INSTRUCTIONS:
1. Use the available variables from context
2. Import necessary libraries (pandas as pd, numpy as np, matplotlib.pyplot as plt, etc.)
3. Write clean, efficient code
4. Store the result in a variable called 'result' or 'answer'
5. If you need to create a visualization, use matplotlib or plotly and the result will be automatically captured
6. Return ONLY the Python code, no explanations, no markdown formatting, just the code

Python Code:"""
        
        response = self._call_llm(prompt)
        
        # Extract code from response (remove markdown code blocks if present)
        code = response.strip()
        if code.startswith('```python'):
            code = code[9:]
        elif code.startswith('```'):
            code = code[3:]
        if code.endswith('```'):
            code = code[:-3]
        code = code.strip()
        
        logger.info(f"[LLM Client] Generated code (length: {len(code)} chars)")
        logger.debug(f"[LLM Client] Code:\n{code}")
        
        return code
    
    def _call_gemini(self, prompt: str, system_prompt: Optional[str]) -> str:
        """Invoke Google Gemini API."""
        if not config.GEMINI_KEY:
            raise RuntimeError("GEMINI_KEY is not configured.")
        
        endpoint = config.GEMINI_BASE_URL
        headers = {"Content-Type": "application/json"}
        params = {"key": config.GEMINI_KEY}
        
        system_text = system_prompt or self._default_system_prompt
        combined_prompt = f"{system_text}\n\n{prompt}" if system_text else prompt
        
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": combined_prompt}],
                }
            ],
            "generationConfig": {
                "temperature": config.LLM_TEMPERATURE,
                "maxOutputTokens": config.LLM_MAX_TOKENS,
            },
        }
        
        logger.info(f"[LLM Client] Calling Gemini API...")
        logger.info(f"  Endpoint: {endpoint}")
        logger.info(f"  Prompt length: {len(combined_prompt)} characters")
        
        try:
            response = httpx.post(
                endpoint,
                headers=headers,
                params=params,
                json=payload,
                timeout=config.LLM_REQUEST_TIMEOUT,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error(f"[LLM Client] Gemini API request failed: {exc}")
            raise RuntimeError(f"LLM API request failed: {exc}") from exc
        
        try:
            data = response.json()
        except ValueError as exc:
            logger.error("[LLM Client] Gemini API returned non-JSON response")
            logger.error(f"[LLM Client] Response text: {response.text[:500]}")
            raise RuntimeError("LLM API returned invalid JSON") from exc
        
        try:
            candidates = data["candidates"]
            parts = candidates[0]["content"]["parts"]
            text = "".join(part.get("text", "") for part in parts).strip()
        except (KeyError, IndexError) as exc:
            logger.error(f"[LLM Client] Unexpected Gemini response: {json.dumps(data, indent=2)}")
            raise RuntimeError("Unexpected Gemini response format") from exc
        
        logger.info(f"[LLM Client] Gemini response length: {len(text)} characters")
        return text
    
    def _parse_response(self, response: str) -> Any:
        """Parse LLM response to extract answer."""
        response = (response or "").strip()
        
        if not response:
            return response
        
        # Remove common prefixes/suffixes that LLMs might add
        response = re.sub(r'^(Answer:|The answer is:|Result:|\*\*Answer\*\*:?)\s*', '', response, flags=re.IGNORECASE)
        response = response.strip()
        
        # Remove markdown code blocks if present
        response = re.sub(r'```[a-z]*\n?', '', response)
        response = re.sub(r'```', '', response)
        response = response.strip()
        
        # Try JSON first (if response looks like JSON)
        if response.startswith('{') or response.startswith('['):
            try:
                parsed = json.loads(response)
                return parsed
            except json.JSONDecodeError:
                pass
        
        # Try to extract JSON from response text
        json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response)
        if json_match:
            try:
                parsed = json.loads(json_match.group(0))
                return parsed
            except json.JSONDecodeError:
                pass
        
        # Try numbers (handle numbers with text around them)
        number_match = re.search(r'-?\d+\.?\d*', response)
        if number_match:
            num_str = number_match.group(0)
            try:
                if "." in num_str:
                    return float(num_str)
                return int(num_str)
            except ValueError:
                pass
        
        # Try booleans
        lowered = response.lower().strip()
        if lowered in {"true", "yes", "correct", "1"}:
            return True
        if lowered in {"false", "no", "incorrect", "0"}:
            return False
        
        return response

