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
            "input": "name_of_previous_step_result"
        }}
    ]
}}

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
        if self.provider == "aipipe":
            return self._call_aipipe(prompt, system_prompt)
        
        raise ValueError(f"Unsupported LLM provider: {self.provider}")
    
    def _call_aipipe(self, prompt: str, system_prompt: Optional[str]) -> str:
        """Invoke AiPipe chat completions endpoint."""
        if not config.AIPIPE_API_KEY:
            raise RuntimeError("AIPIPE_API_KEY is not configured.")
        
        base_url = (config.AIPIPE_BASE_URL or "").rstrip("/")
        endpoint = f"{base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {config.AIPIPE_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": config.AIPIPE_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt or self._default_system_prompt,
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": config.LLM_TEMPERATURE,
            "max_tokens": config.LLM_MAX_TOKENS,
        }
        
        logger.info(f"[LLM Client] Calling AiPipe API...")
        logger.info(f"  Endpoint: {endpoint}")
        logger.info(f"  Model: {config.AIPIPE_MODEL}")
        logger.info(f"  Prompt length: {len(prompt)} characters")
        logger.info(f"  Prompt preview: {prompt[:200]}..." if len(prompt) > 200 else f"  Prompt: {prompt}")
        
        try:
            response = httpx.post(
                endpoint,
                json=payload,
                headers=headers,
                timeout=config.LLM_REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            logger.info(f"[LLM Client] AiPipe API call successful (Status: {response.status_code})")
        except httpx.HTTPError as exc:
            logger.error(f"[LLM Client] AiPipe API request failed: {exc}")
            logger.error(f"[LLM Client] Check your network connection and AIPIPE_API_KEY configuration")
            raise RuntimeError(f"LLM API request failed: {exc}") from exc
        
        try:
            data = response.json()
            logger.info(f"[LLM Client] AiPipe API response received")
        except ValueError as exc:
            logger.error(f"[LLM Client] AiPipe API returned non-JSON response")
            logger.error(f"[LLM Client] Response text: {response.text[:500]}")
            raise RuntimeError(f"LLM API returned invalid response: {exc}") from exc
        
        choices = data.get("choices", [])
        if not choices:
            logger.error(f"[LLM Client] AiPipe API response missing choices")
            logger.error(f"[LLM Client] Full response: {json.dumps(data, indent=2)}")
            raise RuntimeError("LLM API response missing choices")
        
        message = choices[0].get("message", {})
        content = message.get("content")
        if isinstance(content, list):
            # Some APIs return list of segments
            content = " ".join(
                segment.get("text", "") if isinstance(segment, dict) else str(segment)
                for segment in content
            ).strip()
        
        elif isinstance(content, (dict,)):
            content = content.get("text", "")
        
        logger.info(f"[LLM Client] LLM response content:")
        logger.info(f"  Length: {len(str(content))} characters")
        logger.info(f"  Content: {str(content)[:500]}..." if len(str(content)) > 500 else f"  Content: {content}")
        
        return (content or "").strip()
    
    def _parse_response(self, response: str) -> Any:
        """Parse LLM response to extract answer."""
        response = response.strip()
        
        # Try to parse as JSON
        try:
            return json.loads(response)
        except:
            pass
        
        # Try to parse as number
        try:
            if '.' in response:
                return float(response)
            else:
                return int(response)
        except:
            pass
        
        # Try to parse as boolean
        if response.lower() in ['true', 'yes']:
            return True
        if response.lower() in ['false', 'no']:
            return False
        
        # Return as string
        return response

