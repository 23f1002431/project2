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

logger = logging.getLogger(__name__)


class LLMClient:
    """Client for interacting with LLM APIs."""
    
    def __init__(self, provider: str = None):
        self.provider = (provider or config.DEFAULT_LLM_PROVIDER).lower()
        self._default_system_prompt = (
            "You are a helpful assistant that solves data analysis tasks."
        )
    
    async def analyze_task(self, quiz_text: str) -> Dict[str, Any]:
        """
        Analyze quiz task and create a step-by-step plan.
        """
        logger.info(f"[LLM Client] Analyzing quiz task...")
        logger.info(f"[LLM Client] Quiz text sent to LLM:")
        logger.info(f"  {quiz_text[:300]}..." if len(quiz_text) > 300 else f"  {quiz_text}")
        
        prompt = f"""Analyze this quiz task and create a detailed step-by-step plan to solve it.

Quiz Task:
{quiz_text}

Create a JSON plan with the following structure:
{{
    "steps": [
        {{
            "type": "download_file|scrape_data|api_call|process_data|analyze_data|visualize|llm_reasoning",
            "description": "what to do in this step",
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

IMPORTANT for api_call steps:
- If the description mentions "POST" or "post", set "method": "POST"
- If the quiz text contains a JSON payload to send, extract it and include it in the "json" field
- Always include the "method" field for api_call steps

Return only valid JSON."""
        
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
        
        prompt = f"""Solve this task step:
{description}
{context_str}

Provide a clear, concise answer. If the answer is a number, return only the number. If it's text, return the text. If it's a boolean, return true or false."""
        
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
        results_summary = {}
        for key, value in intermediate_results.items():
            if isinstance(value, (str, int, float, bool)):
                results_summary[key] = value
            elif isinstance(value, pd.DataFrame):
                results_summary[key] = f"DataFrame with shape {value.shape}"
            else:
                results_summary[key] = str(type(value).__name__)
        
        prompt = f"""Based on the quiz task and intermediate results, extract the final answer.

Quiz Task:
{quiz_text}

Intermediate Results:
{json.dumps(results_summary, indent=2)}

Determine the answer format (number, string, boolean, base64 image, or JSON object) and provide the answer.
If it's a number, return only the number.
If it's a string, return the string.
If it's a boolean, return true or false.
If it's an image, describe how to generate it.
If it's JSON, return valid JSON."""
        
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
    
    def _call_llm(self, prompt: str, system_prompt: str = None) -> str:
        """Make API call to configured LLM provider."""
        logger.debug(f"[LLM Client] Calling LLM with provider: {self.provider}")
        if self.provider == "gemini":
            return self._call_gemini(prompt, system_prompt)
        
        raise ValueError(f"Unsupported LLM provider: {self.provider}")
    
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
        
        # Try JSON
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass
        
        # Try numbers
        try:
            if "." in response:
                return float(response)
            return int(response)
        except ValueError:
            pass
        
        # Try booleans
        lowered = response.lower()
        if lowered in {"true", "yes"}:
            return True
        if lowered in {"false", "no"}:
            return False
        
        return response

