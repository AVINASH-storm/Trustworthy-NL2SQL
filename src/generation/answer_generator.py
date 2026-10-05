"""
Natural Language Answer Generation Engine.
Synthesizes executed database query results into clear, concise, and business-focused explanations
using Gemini API or structured deterministic formatting.
"""

import os
from typing import Any, Dict, Optional
from dotenv import load_dotenv
import pandas as pd

load_dotenv()

try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False


ANSWER_SYSTEM_INSTRUCTION = """You are an executive data analyst presenting query findings to a business stakeholder.
Your job is to translate SQL query results into a clear, direct, and factual natural language answer.

RULES:
1. Ground your answer STRICTLY in the provided Query Results table. Never invent or speculate on numbers not in the data.
2. Directly answer the user's question in the first 1-2 sentences.
3. Highlight key metrics (totals, averages, top entities).
4. If the result is empty, clearly state that no records met the specified criteria.
5. Keep the tone professional, concise, and executive.
"""


class AnswerGenerator:
    """Generates natural language business summaries from SQL query results."""

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or os.environ.get("GEMINI_MODEL") or "gemini-3.8-flash"
        self.api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        self.client = None
        if self.api_key and GENAI_AVAILABLE:
            try:
                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                print(f"[Warning] Failed to initialize Gemini Client for answers: {e}")

    def generate_answer(self, question: str, sql: str, df: pd.DataFrame) -> str:
        """Generate executive answer summarizing the query result."""
        if df.empty:
            return "The database query executed successfully, but returned 0 matching records for your question."

        # Convert top 10 rows of DataFrame to markdown table
        data_table_str = df.head(10).to_markdown(index=False)
        total_rows = len(df)

        prompt = f"""=== USER QUESTION ===
{question}

=== EXECUTED SQL ===
```sql
{sql}
```

=== QUERY RESULTS (Total rows: {total_rows}) ===
{data_table_str}

Please summarize the answer to the user's question based strictly on these results.
"""

        if self.client:
            try:
                interaction = self.client.interactions.create(
                    model=self.model_name,
                    input=prompt,
                    system_instruction=ANSWER_SYSTEM_INSTRUCTION
                )
                return interaction.output_text.strip()
            except Exception:
                try:
                    res = self.client.models.generate_content(
                        model=self.model_name,
                        contents=prompt,
                    )
                    return res.text.strip()
                except Exception:
                    pass

        # Offline fallback: structured factual summary
        return self._format_offline_summary(question, df)

    def _format_offline_summary(self, question: str, df: pd.DataFrame) -> str:
        """Deterministic summary generator when offline."""
        num_rows = len(df)
        cols = list(df.columns)
        first_row = df.iloc[0].to_dict()

        if num_rows == 1 and len(cols) == 1:
            val = list(first_row.values())[0]
            metric = cols[0].replace("_", " ").title()
            return f"Based on the database records, the total {metric} is **{val:,}**." if isinstance(val, (int, float)) else f"The result is **{val}**."

        summary_lines = [f"Found **{num_rows}** matching record{'s' if num_rows != 1 else ''}."]
        if num_rows > 0:
            top_entity = list(first_row.items())[0]
            val_entity = list(first_row.items())[1] if len(first_row) > 1 else None
            if val_entity:
                summary_lines.append(f"Top entry: **{top_entity[0]}** `{top_entity[1]}` with **{val_entity[0]}** = `{val_entity[1]}`.")

        return " ".join(summary_lines)
