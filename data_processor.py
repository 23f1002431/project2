"""
Data Processor Module
Handles data downloading, processing, analysis, and visualization.
"""
import io
import base64
import re
from typing import Dict, Any, Optional, List
import httpx
import pandas as pd
import numpy as np
from PIL import Image
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.graph_objects as go
import plotly.express as px
import PyPDF2
import pdfplumber


class DataProcessor:
    """Handles data processing tasks."""
    
    async def download_file(self, url: str) -> bytes:
        """Download file from URL."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.content
    
    async def call_api(
        self, 
        url: str, 
        headers: Dict[str, str] = None,
        method: str = "GET",
        data: Any = None,
        json_data: Any = None
    ) -> Any:
        """
        Make API call (GET or POST) and return response.
        
        Args:
            url: API endpoint URL
            headers: Optional headers dictionary
            method: HTTP method ("GET" or "POST"), defaults to "GET"
            data: Optional data for POST requests (form data, bytes, etc.)
            json_data: Optional JSON data for POST requests (will be sent as JSON)
        
        Returns:
            Parsed JSON response if possible, otherwise text response
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            if method.upper() == "POST":
                if json_data is not None:
                    # Send as JSON
                    response = await client.post(
                        url, 
                        headers=headers or {},
                        json=json_data
                    )
                elif data is not None:
                    # Send as form data or raw data
                    response = await client.post(
                        url,
                        headers=headers or {},
                        data=data
                    )
                else:
                    # POST with no body
                    response = await client.post(
                        url,
                        headers=headers or {}
                    )
            else:
                # Default to GET
                response = await client.get(url, headers=headers or {})
            
            response.raise_for_status()
            try:
                return response.json()
            except:
                return response.text
    
    async def process_data(self, data: Any, instructions: str) -> Any:
        """
        Process data based on instructions.
        Handles cleaning, transformation, etc.
        """
        if isinstance(data, bytes):
            # Try to parse as various formats
            # PDF
            if data.startswith(b'%PDF'):
                return await self._process_pdf(data, instructions)
            # Image
            try:
                img = Image.open(io.BytesIO(data))
                return await self._process_image(img, instructions)
            except:
                pass
            # Text
            try:
                text = data.decode('utf-8')
                return await self._process_text(text, instructions)
            except:
                pass
        
        elif isinstance(data, str):
            return await self._process_text(data, instructions)
        
        elif isinstance(data, pd.DataFrame):
            return await self._process_dataframe(data, instructions)
        
        elif isinstance(data, list):
            # Try to convert to DataFrame
            try:
                df = pd.DataFrame(data)
                return await self._process_dataframe(df, instructions)
            except:
                return data
        
        return data
    
    async def _process_pdf(self, pdf_data: bytes, instructions: str) -> Any:
        """Process PDF file."""
        results = []
        
        # Try pdfplumber first (better for tables)
        try:
            pdf = pdfplumber.open(io.BytesIO(pdf_data))
            for page in pdf.pages:
                text = page.extract_text()
                tables = page.extract_tables()
                results.append({
                    "page": page.page_number,
                    "text": text,
                    "tables": tables
                })
            pdf.close()
            return results
        except:
            pass
        
        # Fallback to PyPDF2
        try:
            pdf = PyPDF2.PdfReader(io.BytesIO(pdf_data))
            text = ""
            for page in pdf.pages:
                text += page.extract_text() + "\n"
            return text
        except:
            return None
    
    async def _process_image(self, img: Image.Image, instructions: str) -> Any:
        """Process image."""
        # For now, return image as-is
        # Could add OCR, object detection, etc.
        return img
    
    async def _process_text(self, text: str, instructions: str) -> Any:
        """Process text data."""
        # Basic text cleaning
        if "clean" in instructions.lower():
            # Remove extra whitespace
            text = re.sub(r'\s+', ' ', text)
            # Remove special characters if needed
            if "remove special" in instructions.lower():
                text = re.sub(r'[^\w\s]', '', text)
        
        # Try to extract structured data
        if "table" in instructions.lower() or "csv" in instructions.lower():
            # Try to parse as CSV
            try:
                df = pd.read_csv(io.StringIO(text))
                return df
            except:
                pass
        
        return text
    
    async def _process_dataframe(self, df: pd.DataFrame, instructions: str) -> pd.DataFrame:
        """Process DataFrame."""
        # Handle common transformations
        if "drop na" in instructions.lower() or "remove null" in instructions.lower():
            df = df.dropna()
        
        if "drop duplicates" in instructions.lower():
            df = df.drop_duplicates()
        
        # Column operations
        if "rename" in instructions.lower():
            # Extract rename instructions (simplified)
            pass
        
        # Type conversions
        if "convert" in instructions.lower():
            # Try to infer and convert types
            for col in df.columns:
                try:
                    df[col] = pd.to_numeric(df[col], errors='ignore')
                except:
                    pass
        
        return df
    
    async def analyze_data(self, data: Any, instructions: str) -> Any:
        """
        Analyze data: filtering, sorting, aggregation, statistics.
        """
        # Convert to DataFrame if possible
        df = None
        if isinstance(data, pd.DataFrame):
            df = data
        elif isinstance(data, list):
            try:
                df = pd.DataFrame(data)
            except:
                pass
        elif isinstance(data, dict):
            try:
                df = pd.DataFrame([data])
            except:
                pass
        
        if df is None:
            return data
        
        # Filter
        if "filter" in instructions.lower():
            # Extract filter conditions (simplified - would need more sophisticated parsing)
            # For now, return filtered data based on common patterns
            pass
        
        # Sort
        if "sort" in instructions.lower():
            # Extract sort column and direction
            sort_match = re.search(r'sort\s+by\s+(\w+)', instructions.lower())
            if sort_match:
                col = sort_match.group(1)
                if col in df.columns:
                    ascending = "desc" not in instructions.lower()
                    df = df.sort_values(by=col, ascending=ascending)
        
        # Aggregate
        if "sum" in instructions.lower():
            # Find column to sum
            sum_match = re.search(r'sum\s+of\s+["\']?(\w+)["\']?', instructions.lower())
            if sum_match:
                col = sum_match.group(1)
                if col in df.columns:
                    return float(df[col].sum())
            # Default: sum all numeric columns
            numeric_cols = df.select_dtypes(include=[np.number]).columns
            if len(numeric_cols) == 1:
                return float(df[numeric_cols[0]].sum())
        
        if "mean" in instructions.lower() or "average" in instructions.lower():
            mean_match = re.search(r'(?:mean|average)\s+of\s+["\']?(\w+)["\']?', instructions.lower())
            if mean_match:
                col = mean_match.group(1)
                if col in df.columns:
                    return float(df[col].mean())
        
        if "count" in instructions.lower():
            return len(df)
        
        if "max" in instructions.lower():
            max_match = re.search(r'max\s+of\s+["\']?(\w+)["\']?', instructions.lower())
            if max_match:
                col = max_match.group(1)
                if col in df.columns:
                    return float(df[col].max())
        
        if "min" in instructions.lower():
            min_match = re.search(r'min\s+of\s+["\']?(\w+)["\']?', instructions.lower())
            if min_match:
                col = min_match.group(1)
                if col in df.columns:
                    return float(df[col].min())
        
        # Statistical analysis
        if "statistics" in instructions.lower() or "stats" in instructions.lower():
            return df.describe().to_dict()
        
        return df
    
    async def create_visualization(
        self, 
        data: Any, 
        instructions: str
    ) -> str:
        """
        Create visualization and return as base64 encoded image.
        """
        # Convert to DataFrame if needed
        df = None
        if isinstance(data, pd.DataFrame):
            df = data
        elif isinstance(data, list):
            try:
                df = pd.DataFrame(data)
            except:
                pass
        
        if df is None:
            return None
        
        # Determine chart type
        chart_type = "bar"  # default
        if "line" in instructions.lower():
            chart_type = "line"
        elif "scatter" in instructions.lower():
            chart_type = "scatter"
        elif "histogram" in instructions.lower():
            chart_type = "histogram"
        elif "pie" in instructions.lower():
            chart_type = "pie"
        
        # Create visualization
        fig = None
        
        if chart_type == "bar":
            if len(df.columns) >= 2:
                fig = px.bar(df, x=df.columns[0], y=df.columns[1])
            else:
                fig = px.bar(df)
        
        elif chart_type == "line":
            if len(df.columns) >= 2:
                fig = px.line(df, x=df.columns[0], y=df.columns[1])
            else:
                fig = px.line(df)
        
        elif chart_type == "scatter":
            if len(df.columns) >= 2:
                fig = px.scatter(df, x=df.columns[0], y=df.columns[1])
            else:
                fig = px.scatter(df)
        
        elif chart_type == "histogram":
            if len(df.columns) >= 1:
                fig = px.histogram(df, x=df.columns[0])
            else:
                fig = px.histogram(df)
        
        elif chart_type == "pie":
            if len(df.columns) >= 2:
                fig = px.pie(df, names=df.columns[0], values=df.columns[1])
            else:
                fig = px.pie(df)
        
        if fig:
            # Convert to base64
            img_bytes = fig.to_image(format="png")
            return base64.b64encode(img_bytes).decode('utf-8')
        
        return None

