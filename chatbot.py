"""
chatbot.py  -  the same question, sent to a plain chatbot.

No tools, no database. It has never seen your data, so all it can do is guess.
Compare it with agent.py, which can look at the tables and run SQL.

RUN IT
  python chatbot.py "Why did our orders drop in Mumbai last week?"
"""
import os
import sys

from dotenv import load_dotenv
from groq import Groq

import show

load_dotenv()   # picks up GROQ_API_KEY from .env

QUESTION = sys.argv[1]
MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")   # same model as agent.py

client = Groq()   # reads GROQ_API_KEY from your environment
response = client.chat.completions.create(
    model=MODEL,
    max_tokens=500,
    messages=[
        {"role": "system", "content": "You work at a food delivery company in India. Answer in one short paragraph."},
        {"role": "user", "content": QUESTION},   # just the question. No tools, no data.
    ],
)
answer = response.choices[0].message.content
show.chatbot(QUESTION, answer)
