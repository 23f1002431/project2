"""
Sandboxed Python Code Execution Module
Safely executes dynamically generated Python code in a restricted environment.
"""
import ast
import sys
import io
import contextlib
import logging
from typing import Any, Dict, Optional
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import seaborn as sns
import base64

logger = logging.getLogger(__name__)


class RestrictedExecutionContext:
    """Restricted execution context for safe code execution."""
    
    # Allowed modules and functions
    ALLOWED_BUILTINS = {
        'abs', 'all', 'any', 'bool', 'dict', 'enumerate', 'float', 'int',
        'len', 'list', 'max', 'min', 'range', 'round', 'sorted', 'str',
        'sum', 'tuple', 'zip', 'print', 'type', 'isinstance', 'hasattr',
        'getattr', 'setattr', 'repr', 'dir', 'vars', 'open'
    }
    
    ALLOWED_MODULES = {
        'math', 'random', 'datetime', 'json', 'base64', 'io', 'collections',
        'itertools', 'functools', 'operator', 're', 'string'
    }
    
    def __init__(self):
        self.vars = {}
        self._setup_allowed_modules()
    
    def _setup_allowed_modules(self):
        """Setup allowed modules in the context."""
        for mod_name in self.ALLOWED_MODULES:
            try:
                self.vars[mod_name] = __import__(mod_name)
            except ImportError:
                pass
        
        # Add data science libraries
        self.vars['np'] = np
        self.vars['pd'] = pd
        self.vars['plt'] = plt
        self.vars['sns'] = sns
        self.vars['base64'] = base64
        self.vars['Image'] = __import__('PIL.Image', fromlist=['Image'])
    
    def validate_code(self, code: str) -> bool:
        """Validate that code doesn't contain dangerous operations."""
        dangerous_patterns = [
            'import os',
            'import sys',
            'import subprocess',
            'import shutil',
            'import socket',
            '__import__',
            'exec(',
            'eval(',
            'compile(',
            'open(',
            'file(',
            'input(',
            'raw_input(',
        ]
        
        code_lower = code.lower()
        for pattern in dangerous_patterns:
            if pattern in code_lower:
                logger.warning(f"Potentially dangerous code pattern detected: {pattern}")
                return False
        
        # Try to parse the code
        try:
            ast.parse(code)
        except SyntaxError as e:
            logger.error(f"Syntax error in code: {e}")
            return False
        
        return True
    
    def execute(self, code: str, timeout: int = 30) -> Dict[str, Any]:
        """
        Execute code in restricted environment.
        Returns dict with 'result', 'output', 'error', and 'plot' keys.
        """
        if not self.validate_code(code):
            return {
                'error': 'Code validation failed: contains dangerous operations',
                'result': None,
                'output': '',
                'plot': None
            }
        
        # Create restricted globals
        restricted_globals = {
            '__builtins__': {name: getattr(__builtins__, name) 
                           for name in self.ALLOWED_BUILTINS 
                           if hasattr(__builtins__, name)},
            **self.vars
        }
        
        # Capture stdout
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()
        
        result = None
        error = None
        plot_base64 = None
        
        try:
            with contextlib.redirect_stdout(stdout_capture):
                with contextlib.redirect_stderr(stderr_capture):
                    # Compile and execute
                    compiled = compile(code, '<string>', 'exec')
                    exec(compiled, restricted_globals, self.vars)
                    
                    # Try to get result if 'result' variable exists
                    if 'result' in self.vars:
                        result = self.vars['result']
                    elif 'answer' in self.vars:
                        result = self.vars['answer']
            
            # Check if a plot was created
            if plt.get_fignums():
                # Save plot to bytes
                buf = io.BytesIO()
                plt.savefig(buf, format='png', bbox_inches='tight')
                buf.seek(0)
                plot_base64 = base64.b64encode(buf.read()).decode('utf-8')
                plt.close('all')  # Close all figures
            
            output = stdout_capture.getvalue()
            stderr_output = stderr_capture.getvalue()
            
            if stderr_output:
                logger.warning(f"Code execution stderr: {stderr_output}")
                if not error:
                    error = stderr_output
            
        except Exception as e:
            error = str(e)
            logger.error(f"Code execution error: {error}")
        
        return {
            'result': result,
            'output': stdout_capture.getvalue(),
            'error': error,
            'plot': plot_base64
        }


class CodeExecutor:
    """Main code executor class."""
    
    def __init__(self):
        self.context = RestrictedExecutionContext()
    
    async def execute_code(self, code: str, timeout: int = 30) -> Dict[str, Any]:
        """
        Execute Python code safely.
        
        Args:
            code: Python code string to execute
            timeout: Maximum execution time in seconds
        
        Returns:
            Dictionary with execution results
        """
        logger.info(f"[Code Executor] Executing code (length: {len(code)} chars)...")
        logger.debug(f"[Code Executor] Code:\n{code}")
        
        result = self.context.execute(code, timeout)
        
        if result['error']:
            logger.error(f"[Code Executor] Execution error: {result['error']}")
        else:
            logger.info(f"[Code Executor] Code executed successfully")
            if result['result'] is not None:
                logger.info(f"[Code Executor] Result: {result['result']} (type: {type(result['result']).__name__})")
            if result['plot']:
                logger.info(f"[Code Executor] Plot generated (base64 length: {len(result['plot'])} chars)")
        
        return result
    
    async def execute_analysis(self, data: Any, instructions: str) -> Any:
        """
        Use LLM to generate and execute code for data analysis.
        This is a placeholder - in a real implementation, you'd call LLM to generate code.
        """
        # This would typically use LLM to generate code based on instructions
        # For now, return the data as-is
        return data

