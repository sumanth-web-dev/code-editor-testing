import os
import google.generativeai as genai
from dotenv import load_dotenv
from openai import OpenAI
from flask import jsonify
import json


load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel(model_name="gemini-1.5-flash", generation_config={"temperature": 0.7})


def generate_questions(prompt, num_questions=5):
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(
            f"{prompt}. Return exactly {num_questions} questions in JSON format: "
            "{'questions': ['q1', 'q2', ...]}"
        )
        
        # Extract JSON from response
        try:
            start = response.text.find('{')
            end = response.text.rfind('}') + 1
            json_str = response.text[start:end]
            data = json.loads(json_str)
            return data.get('questions', [])[:num_questions]
        except:
            # Fallback if JSON parsing fails
            questions = [line.strip() for line in response.text.split('\n') 
                        if line.strip() and len(line) > 10][:num_questions]
            return questions
            
    except Exception as e:
        print(f"Error generating questions: {str(e)}")
        return [f"Technical question {i+1}" for i in range(num_questions)]

def evaluate_answer(question, answer):
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"""
        Evaluate this interview answer and provide:
        1. An ideal answer (2-3 sentences)
        2. A score (0-100)
        
        Format as JSON:
        {{
            "ideal_answer": "...",
            "score": 85
        }}
        
        Question: {question}
        Answer: {answer}
        """
        
        response = model.generate_content(prompt)
        
        # Extract JSON from response
        try:
            start = response.text.find('{')
            end = response.text.rfind('}') + 1
            json_str = response.text[start:end]
            data = json.loads(json_str)
            return data.get('ideal_answer', ''), data.get('score', 0)
        except:
            return "Evaluation not available", 0
            
    except Exception as e:
        print(f"Error evaluating answer: {str(e)}")
        return "Evaluation error", 0
    

