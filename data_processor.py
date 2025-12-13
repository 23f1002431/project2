"""
Data Processor Module
Handles data downloading, processing, analysis, and visualization.
"""
import io
import base64
import re
import json
import os
import tempfile
import shutil
from typing import Dict, Any, Optional, List
import httpx
import pandas as pd
import numpy as np
from PIL import Image
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.graph_objects as go
import plotly.express as px
import PyPDF2
import pdfplumber
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)


class DataProcessor:
    """Handles data processing tasks."""
    
    def __init__(self):
        self.temp_dir = tempfile.mkdtemp(prefix="quiz_solver_")
        logger.info(f"[Data Processor] Initialized with temp directory: {self.temp_dir}")
    
    def __del__(self):
        """Cleanup temp directory on destruction."""
        if hasattr(self, 'temp_dir') and os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir)
                logger.debug(f"[Data Processor] Cleaned up temp directory: {self.temp_dir}")
            except:
                pass
    
    async def download_file(self, url: str, save_path: Optional[str] = None) -> bytes:
        """
        Download file from URL.
        
        Args:
            url: URL to download from
            save_path: Optional path to save file (relative to temp dir)
        
        Returns:
            File content as bytes
        """
        logger.info(f"[Data Processor] Downloading file from: {url}")
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
            content = response.content
            
            if save_path:
                full_path = os.path.join(self.temp_dir, save_path)
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                with open(full_path, 'wb') as f:
                    f.write(content)
                logger.info(f"[Data Processor] File saved to: {full_path}")
            
            return content
    
    def get_temp_file_path(self, filename: str) -> str:
        """Get a path in the temp directory for a file."""
        return os.path.join(self.temp_dir, filename)
    
    def list_downloaded_files(self) -> List[str]:
        """List all files in the temp directory."""
        files = []
        for root, dirs, filenames in os.walk(self.temp_dir):
            for filename in filenames:
                rel_path = os.path.relpath(os.path.join(root, filename), self.temp_dir)
                files.append(rel_path)
        return files
    
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
        """Process PDF file with enhanced table extraction."""
        results = []
        
        # Try pdfplumber first (better for tables)
        try:
            pdf = pdfplumber.open(io.BytesIO(pdf_data))
            all_tables = []
            all_text = []
            
            for page in pdf.pages:
                text = page.extract_text() or ""
                tables = page.extract_tables() or []
                
                # Convert tables to DataFrames if requested
                table_dfs = []
                for table in tables:
                    if table and len(table) > 1:
                        try:
                            # First row as header, rest as data
                            df = pd.DataFrame(table[1:], columns=table[0])
                            table_dfs.append(df)
                        except:
                            table_dfs.append(pd.DataFrame(table))
                
                page_result = {
                    "page": page.page_number,
                    "text": text,
                    "tables": tables,
                    "table_dataframes": table_dfs if table_dfs else None
                }
                results.append(page_result)
                all_tables.extend(table_dfs if table_dfs else [])
                all_text.append(text)
            
            pdf.close()
            
            # If instructions ask for consolidated data, return combined
            if "consolidate" in instructions.lower() or "combine" in instructions.lower():
                if all_tables:
                    # Combine all tables into one DataFrame
                    combined_df = pd.concat(all_tables, ignore_index=True)
                    logger.info(f"[Data Processor] Combined {len(all_tables)} tables into one DataFrame")
                    return combined_df
                elif all_text:
                    return "\n\n".join(all_text)
            
            # Return all pages or just first page based on instructions
            if "first" in instructions.lower() or "single" in instructions.lower():
                return results[0] if results else None
            
            return results if len(results) > 1 else (results[0] if results else None)
        except Exception as e:
            logger.warning(f"[Data Processor] pdfplumber failed: {e}")
        
        # Fallback to PyPDF2
        try:
            pdf = PyPDF2.PdfReader(io.BytesIO(pdf_data))
            text = ""
            for page in pdf.pages:
                text += page.extract_text() + "\n"
            logger.info(f"[Data Processor] Extracted text using PyPDF2 ({len(text)} chars)")
            return text
        except Exception as e:
            logger.error(f"[Data Processor] Failed to process PDF: {e}")
            return None
    
    async def _process_image(self, img: Image.Image, instructions: str) -> Any:
        """Process image."""
        # For now, return image as-is
        # Could add OCR, object detection, etc.
        return img
    
    async def _process_text(self, text: str, instructions: str) -> Any:
        """Process text data with enhanced parsing capabilities."""
        # Basic text cleaning
        if "clean" in instructions.lower():
            # Remove extra whitespace
            text = re.sub(r'\s+', ' ', text)
            # Remove special characters if needed
            if "remove special" in instructions.lower():
                text = re.sub(r'[^\w\s]', '', text)
        
        # Try to parse as JSON
        if "json" in instructions.lower() or text.strip().startswith(('{', '[')):
            try:
                parsed_json = json.loads(text)
                logger.info(f"[Data Processor] Successfully parsed text as JSON")
                return parsed_json
            except json.JSONDecodeError:
                # Try to extract JSON from text
                json_match = re.search(r'\{.*\}', text, re.DOTALL)
                if json_match:
                    try:
                        parsed_json = json.loads(json_match.group(0))
                        logger.info(f"[Data Processor] Extracted and parsed JSON from text")
                        return parsed_json
                    except:
                        pass
        
        # Try to extract HTML tables
        if "table" in instructions.lower() or "html" in instructions.lower():
            try:
                soup = BeautifulSoup(text, 'html.parser')
                tables = soup.find_all('table')
                if tables:
                    dfs = []
                    for table in tables:
                        # Extract table data
                        rows = []
                        for tr in table.find_all('tr'):
                            cells = [td.get_text(strip=True) for td in tr.find_all(['td', 'th'])]
                            if cells:
                                rows.append(cells)
                        if rows:
                            df = pd.DataFrame(rows[1:], columns=rows[0] if len(rows) > 1 else None)
                            dfs.append(df)
                    if dfs:
                        logger.info(f"[Data Processor] Extracted {len(dfs)} HTML table(s)")
                        return dfs[0] if len(dfs) == 1 else dfs
            except Exception as e:
                logger.debug(f"[Data Processor] Failed to parse HTML tables: {e}")
        
        # Try to parse as CSV (multiple formats)
        if "csv" in instructions.lower() or "table" in instructions.lower():
            # Try standard CSV
            try:
                df = pd.read_csv(io.StringIO(text), sep=',')
                logger.info(f"[Data Processor] Successfully parsed text as CSV (comma-separated)")
                return df
            except:
                pass
            
            # Try tab-separated
            try:
                df = pd.read_csv(io.StringIO(text), sep='\t')
                logger.info(f"[Data Processor] Successfully parsed text as TSV (tab-separated)")
                return df
            except:
                pass
            
            # Try pipe-separated
            try:
                df = pd.read_csv(io.StringIO(text), sep='|')
                logger.info(f"[Data Processor] Successfully parsed text as pipe-separated")
                return df
            except:
                pass
        
        return text
    
    async def _process_dataframe(self, df: pd.DataFrame, instructions: str) -> pd.DataFrame:
        """Process DataFrame with enhanced operations."""
        original_shape = df.shape
        
        # Handle common transformations
        if "drop na" in instructions.lower() or "remove null" in instructions.lower():
            df = df.dropna()
            logger.info(f"[Data Processor] Dropped NA values: {original_shape} -> {df.shape}")
        
        if "drop duplicates" in instructions.lower():
            before = len(df)
            df = df.drop_duplicates()
            logger.info(f"[Data Processor] Dropped duplicates: {before} -> {len(df)} rows")
        
        # Column operations
        if "rename" in instructions.lower():
            # Try to extract rename mapping from instructions
            rename_match = re.search(r'rename\s+["\']?(\w+)["\']?\s+to\s+["\']?(\w+)["\']?', instructions.lower())
            if rename_match:
                old_name = rename_match.group(1)
                new_name = rename_match.group(2)
                if old_name in df.columns:
                    df = df.rename(columns={old_name: new_name})
                    logger.info(f"[Data Processor] Renamed column: {old_name} -> {new_name}")
        
        # Type conversions
        if "convert" in instructions.lower():
            # Try to infer and convert types
            for col in df.columns:
                try:
                    # Try numeric first
                    numeric_series = pd.to_numeric(df[col], errors='coerce')
                    if not numeric_series.isna().all():
                        df[col] = numeric_series
                    # Try datetime
                    elif "date" in col.lower() or "time" in col.lower():
                        df[col] = pd.to_datetime(df[col], errors='coerce')
                except:
                    pass
        
        # Filter operations
        if "filter" in instructions.lower():
            # Try to extract filter conditions
            # This is a simplified version - full implementation would parse complex conditions
            filter_match = re.search(r'filter\s+["\']?(\w+)["\']?\s*(>|<|==|!=|>=|<=)\s*([\w.]+)', instructions.lower())
            if filter_match:
                col = filter_match.group(1)
                op = filter_match.group(2)
                value = filter_match.group(3)
                try:
                    value = float(value) if '.' in value else int(value)
                    if col in df.columns:
                        if op == '>':
                            df = df[df[col] > value]
                        elif op == '<':
                            df = df[df[col] < value]
                        elif op == '==':
                            df = df[df[col] == value]
                        logger.info(f"[Data Processor] Filtered: {col} {op} {value}")
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
        Supports multiple chart types and advanced customization.
        """
        logger.info(f"[Data Processor] Creating visualization: {instructions}")
        
        # Convert to DataFrame if needed
        df = None
        if isinstance(data, pd.DataFrame):
            df = data.copy()
        elif isinstance(data, list):
            try:
                df = pd.DataFrame(data)
            except Exception as e:
                logger.warning(f"[Data Processor] Failed to convert list to DataFrame: {e}")
                return None
        elif isinstance(data, dict):
            try:
                df = pd.DataFrame([data])
            except:
                # Try to convert dict of lists/arrays
                try:
                    df = pd.DataFrame(data)
                except:
                    pass
        
        if df is None or df.empty:
            logger.warning("[Data Processor] No valid data for visualization")
            return None
        
        # Determine chart type from instructions
        instructions_lower = instructions.lower()
        chart_type = "bar"  # default
        
        if "scatter" in instructions_lower or "plot" in instructions_lower:
            chart_type = "scatter"
        elif "line" in instructions_lower:
            chart_type = "line"
        elif "histogram" in instructions_lower or "hist" in instructions_lower:
            chart_type = "histogram"
        elif "pie" in instructions_lower:
            chart_type = "pie"
        elif "box" in instructions_lower or "boxplot" in instructions_lower:
            chart_type = "box"
        elif "heatmap" in instructions_lower or "heat map" in instructions_lower:
            chart_type = "heatmap"
        elif "bar" in instructions_lower:
            chart_type = "bar"
        
        # Extract column names if specified
        x_col = None
        y_col = None
        
        # Try to extract column names from instructions
        col_patterns = [
            r'x[:\s]+["\']?(\w+)["\']?',
            r'x-axis[:\s]+["\']?(\w+)["\']?',
            r'horizontal[:\s]+["\']?(\w+)["\']?'
        ]
        for pattern in col_patterns:
            match = re.search(pattern, instructions_lower)
            if match:
                x_col = match.group(1)
                break
        
        col_patterns = [
            r'y[:\s]+["\']?(\w+)["\']?',
            r'y-axis[:\s]+["\']?(\w+)["\']?',
            r'vertical[:\s]+["\']?(\w+)["\']?'
        ]
        for pattern in col_patterns:
            match = re.search(pattern, instructions_lower)
            if match:
                y_col = match.group(1)
                break
        
        # Default column selection
        if not x_col and len(df.columns) > 0:
            x_col = df.columns[0]
        if not y_col and len(df.columns) > 1:
            y_col = df.columns[1]
        
        # Create visualization
        fig = None
        
        try:
            if chart_type == "bar":
                if y_col and x_col and x_col in df.columns and y_col in df.columns:
                    fig = px.bar(df, x=x_col, y=y_col, title=instructions[:100] if len(instructions) > 0 else "Bar Chart")
                elif len(df.columns) >= 2:
                    fig = px.bar(df, x=df.columns[0], y=df.columns[1])
                else:
                    # Single column bar chart
                    fig = px.bar(df, x=df.index, y=df.columns[0])
            
            elif chart_type == "line":
                if y_col and x_col and x_col in df.columns and y_col in df.columns:
                    fig = px.line(df, x=x_col, y=y_col, title=instructions[:100] if len(instructions) > 0 else "Line Chart")
                elif len(df.columns) >= 2:
                    fig = px.line(df, x=df.columns[0], y=df.columns[1])
                else:
                    fig = px.line(df, x=df.index, y=df.columns[0])
            
            elif chart_type == "scatter":
                if y_col and x_col and x_col in df.columns and y_col in df.columns:
                    fig = px.scatter(df, x=x_col, y=y_col, title=instructions[:100] if len(instructions) > 0 else "Scatter Plot")
                elif len(df.columns) >= 2:
                    fig = px.scatter(df, x=df.columns[0], y=df.columns[1])
                else:
                    return None  # Scatter needs at least 2 columns
            
            elif chart_type == "histogram":
                col = x_col if x_col and x_col in df.columns else (df.columns[0] if len(df.columns) > 0 else None)
                if col:
                    fig = px.histogram(df, x=col, title=instructions[:100] if len(instructions) > 0 else "Histogram")
                else:
                    return None
            
            elif chart_type == "pie":
                names_col = x_col if x_col and x_col in df.columns else df.columns[0]
                values_col = y_col if y_col and y_col in df.columns else (df.columns[1] if len(df.columns) > 1 else df.columns[0])
                if names_col in df.columns and values_col in df.columns:
                    fig = px.pie(df, names=names_col, values=values_col, title=instructions[:100] if len(instructions) > 0 else "Pie Chart")
                else:
                    return None
            
            elif chart_type == "box":
                col = y_col if y_col and y_col in df.columns else (df.columns[0] if len(df.columns) > 0 else None)
                if col:
                    fig = px.box(df, y=col, title=instructions[:100] if len(instructions) > 0 else "Box Plot")
                else:
                    return None
            
            elif chart_type == "heatmap":
                # Create correlation heatmap or pivot table heatmap
                numeric_df = df.select_dtypes(include=[np.number])
                if numeric_df.empty:
                    return None
                corr_matrix = numeric_df.corr()
                fig = px.imshow(corr_matrix, title=instructions[:100] if len(instructions) > 0 else "Heatmap")
            
            if fig:
                # Update layout for better appearance
                fig.update_layout(
                    height=600,
                    width=800,
                    template="plotly_white"
                )
                
                # Convert to base64
                img_bytes = fig.to_image(format="png", width=800, height=600, scale=2)
                base64_str = base64.b64encode(img_bytes).decode('utf-8')
                logger.info(f"[Data Processor] Visualization created successfully (base64 length: {len(base64_str)} chars)")
                return base64_str
        
        except Exception as e:
            logger.error(f"[Data Processor] Failed to create visualization: {e}", exc_info=True)
            # Fallback to matplotlib if plotly fails
            try:
                return await self._create_matplotlib_viz(df, chart_type, x_col, y_col)
            except Exception as e2:
                logger.error(f"[Data Processor] Matplotlib fallback also failed: {e2}")
                return None
        
        return None
    
    async def _create_matplotlib_viz(self, df: pd.DataFrame, chart_type: str, x_col: str, y_col: str) -> str:
        """Fallback visualization using matplotlib."""
        plt.figure(figsize=(10, 6))
        
        if chart_type == "bar":
            if y_col and x_col:
                plt.bar(df[x_col], df[y_col])
            else:
                plt.bar(df.index, df.iloc[:, 0])
        
        elif chart_type == "line":
            if y_col and x_col:
                plt.plot(df[x_col], df[y_col])
            else:
                plt.plot(df.index, df.iloc[:, 0])
        
        elif chart_type == "scatter":
            if y_col and x_col:
                plt.scatter(df[x_col], df[y_col])
            else:
                plt.scatter(df.iloc[:, 0], df.iloc[:, 1])
        
        elif chart_type == "histogram":
            col = x_col if x_col else df.columns[0]
            plt.hist(df[col], bins=20)
        
        plt.tight_layout()
        
        # Convert to base64
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', dpi=150)
        buf.seek(0)
        base64_str = base64.b64encode(buf.read()).decode('utf-8')
        plt.close()
        
        return base64_str

