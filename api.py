import os
import json
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from openai import OpenAI
from dotenv import load_dotenv
from googleapiclient.discovery import build

# Load environment variables
load_dotenv()

# Initialize API Clients
openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
custom_search = build("customsearch", "v1", developerKey=os.getenv('GOOGLE_CUSTOM_SEARCH_API_KEY'))

class APIIntegration:
    @staticmethod
    def google_search(query):
        try:
            result = custom_search.cse().list(
                q=query,
                cx=os.getenv('GOOGLE_CUSTOM_SEARCH_CX')
            ).execute()
            
            if 'items' in result:
                # Summarize top 2 search results
                summaries = []
                for item in result['items'][:2]:
                    summaries.append(f"{item['title']}: {item['snippet']}\nLink: {item['link']}")
                return "\n\n".join(summaries)
            return "No search results found."
        except Exception as e:
            return f"Google search error: {str(e)}"

class ConversationManager:
    def __init__(self, max_context_length=10):
        self.max_context_length = max_context_length
        self.full_transcription = [
            {
                "role": "system",
                "content": """You are an advanced AI assistant with access to Google Custom Search API. 
                When a user asks a question, analyze the intent and decide to use the search API.
                
                Respond ONLY with a JSON in this exact format:
                {
                    "api": "google_search|none",
                    "query": "specific search term"
                }
                
                - Use "google_search" for queries that need web search information
                - Use "none" for general conversation or unclear requests
                
                Examples:
                - "What is the capital of France?" → {"api": "google_search", "query": "capital of France"}
                - "What's the weather in London?" → {"api": "google_search", "query": "current weather in London"}
                - "Tell me a joke" → {"api": "none"}"""
            }
        ]

    def add_message(self, role, content):
        self.full_transcription.append({"role": role, "content": content})
        
        if len(self.full_transcription) > self.max_context_length:
            self.full_transcription = self.full_transcription[:1] + self.full_transcription[-self.max_context_length:]

    def get_messages(self):
        return self.full_transcription

app = FastAPI()
conversation_manager = ConversationManager()
api_integration = APIIntegration()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            try:
                data = await websocket.receive_text()
                user_input = data.strip()

                # Add user message to conversation
                conversation_manager.add_message("user", user_input)

                # Get API routing from OpenAI
                routing_response = openai_client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=conversation_manager.get_messages(),
                    response_format={"type": "json_object"}
                )

                # Parse the API routing JSON
                try:
                    api_routing = json.loads(routing_response.choices[0].message.content)
                except json.JSONDecodeError:
                    # Fallback to general conversation
                    response_obj = openai_client.chat.completions.create(
                        model="gpt-3.5-turbo",
                        messages=conversation_manager.get_messages()
                    )
                    response = response_obj.choices[0].message.content
                    await websocket.send_text(response)
                    continue

                # Route to appropriate API
                if api_routing.get('api') == 'google_search':
                    response = api_integration.google_search(api_routing.get('query', ''))
                else:
                    # Default to OpenAI for general conversation
                    response_obj = openai_client.chat.completions.create(
                        model="gpt-3.5-turbo",
                        messages=conversation_manager.get_messages()
                    )
                    response = response_obj.choices[0].message.content

                # Add AI response to conversation
                conversation_manager.add_message("assistant", response)

                # Send response back to client
                await websocket.send_text(response)

            except Exception as e:
                print(f"Processing error: {e}")
                error_response = f"Sorry, I encountered an error: {str(e)}"
                await websocket.send_text(error_response)

    except WebSocketDisconnect:
        print("WebSocket disconnected")
    except Exception as e:
        print(f"Unexpected WebSocket error: {e}")
    finally:
        try:
            await websocket.close(code=1000)
        except Exception:
            pass

# CORS Configuration
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)