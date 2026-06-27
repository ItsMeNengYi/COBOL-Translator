import os
from dotenv import load_dotenv

from openai import OpenAI

load_dotenv() 

class OpenAIAgent:
    def __init__(self, api_key: str = os.getenv("OPENAI_API_KEY"), system_prompt="You are a helpful assistant.", model="gpt-4o-mini"):
        # Initializes the client with the provided key. 
        # If api_key is None, it will automatically look for the OPENAI_API_KEY environment variable.
        self.client = OpenAI(api_key=api_key)
        self.model = model
        
        # Initialize conversation history with the system prompt
        self.messages = [
            {"role": "system", "content": system_prompt}
        ]

    def chat(self, user_prompt: str) -> str:
        """Sends a message to the LLM, updates history, and returns the response."""
        # Append user message to history
        self.messages.append({"role": "user", "content": user_prompt})
        
        try:
            # Make the API call
            response = self.client.chat.completions.create(
                model=self.model,
                messages=self.messages
            )
            
            # Extract the text reply
            assistant_reply = response.choices[0].message.content
            
            # Append assistant's reply to history so it remembers context
            self.messages.append({"role": "assistant", "content": assistant_reply})
            
            return assistant_reply
            
        except Exception as e:
            return f"Error communicating with OpenAI: {e}"

# --- Testing the Agent ---
if __name__ == "__main__":
    agent = OpenAIAgent()
    reply = agent.chat("Hello testing123")
    print(f"\nAgent: {reply}\n")
    
            