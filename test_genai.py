import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

model = genai.GenerativeModel("gemini-1.5-flash")

try:
    print("Making request...")
    from google.api_core.retry import Retry
    response = model.generate_content("hello", request_options={"retry": None})
    print("Success:", response.text)
except Exception as e:
    print("Error:", type(e), str(e))
