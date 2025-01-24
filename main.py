import os
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

class ConversationManager:
    def __init__(self, max_context_length=10):
        self.max_context_length = max_context_length
        self.full_transcription = [
            {
                "role": "system",
                "content": "You are Jarvis, a helpful personal AI assistant from the Iron Man movies. Respond concisely and with a technological sophistication. Always be ready to listen and help."
            }
        ]

    def add_message(self, role, content):
        self.full_transcription.append({"role": role, "content": content})
        
        if len(self.full_transcription) > self.max_context_length:
            self.full_transcription = self.full_transcription[:1] + self.full_transcription[-self.max_context_length:]

    def get_messages(self):
        return self.full_transcription

conversation_manager = ConversationManager()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            try:
                data = await websocket.receive_text()
                user_input = data.strip()

                conversation_manager.add_message("user", user_input)

                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=conversation_manager.get_messages()
                )
                ai_response = response.choices[0].message.content

                conversation_manager.add_message("assistant", ai_response)

                await websocket.send_text(ai_response)

            except Exception as e:
                print(f"Processing error: {e}")
                break

    except WebSocketDisconnect:
        print("WebSocket disconnected")
    except Exception as e:
        print(f"Unexpected WebSocket error: {e}")
    finally:
        try:
            await websocket.close(code=1000)
        except Exception:
            pass

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)