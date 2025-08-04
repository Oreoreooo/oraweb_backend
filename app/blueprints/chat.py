import requests
from app.extension import db
from app.models import Conversation, ChatMessage
from ..config import Config

class AIService:
    @staticmethod
    def regenerate_text(current_content, new_content):
        try:
            print(f"Regenerate text request - Current: '{current_content}', New: '{new_content}'")
            
            prompt = ''
            if not current_content:
                prompt = f'Please help improve the fluency of this text: "{new_content}". Return ONLY the improved text without any additional commentary or explanations.'
            else:
                prompt = f'Please combine and improve the fluency of these two texts. You can make some adjustment to make it more fluent. First text: "{current_content}". Second text: "{new_content}". Return ONLY the improved text without any additional commentary or explanations.'

            print(f"Sending regeneration request to AI API...")
            response = requests.post(
                'https://open.bigmodel.cn/api/paas/v4/chat/completions',
                json={
                    'model': 'glm-4-plus',
                    'messages': [
                        {
                            'role': 'system',
                            'content': "You are an assistant who helps improve text fluency.No other additional information should be added.Return ONLY the improved text without any additional commentary, explanations, or formatting."
                        },
                        {
                            'role': 'user',
                            'content': prompt
                        }
                    ]
                },
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {Config.CHAT_API_KEY}'
                },
                timeout=30
            )
            
            print(f"Regeneration API Response status: {response.status_code}")
            response_data = response.json()
            
            if not response.ok:
                print(f"Regeneration API Error response: {response_data}")
                raise Exception(f"API Error: {response_data.get('error', 'Unknown error')}")
            
            if 'choices' not in response_data or not response_data['choices']:
                print(f"Invalid regeneration response format: {response_data}")
                raise Exception("No response from AI model")
                
            result = response_data['choices'][0]['message']['content'].strip()
            print(f"Regeneration successful: '{result}'")
            return result
        except requests.exceptions.Timeout:
            print("Regeneration request timeout error")
            raise Exception("Request timeout - please try again")
        except requests.exceptions.ConnectionError:
            print("Regeneration connection error")
            raise Exception("Network connection error - please check your internet connection")
        except requests.exceptions.RequestException as e:
            print(f"Regeneration request error: {str(e)}")
            raise Exception(f"Network error: {str(e)}")
        except Exception as e:
            print(f"Regeneration error: {str(e)}")
            raise Exception(f"Failed to regenerate text: {str(e)}")

    @staticmethod
    def chat(messages):
        try:
            # 添加详细的日志记录
            print(f"Chat request - Messages count: {len(messages)}")
            
            if not any(msg.get('role') == 'system' for msg in messages):
                messages.insert(0, {
                    'role': 'system',
                    'content': "As a professional 'Life Story Architect,' you'll blend oral history methodology with narrative therapy techniques to help users construct comprehensive autobiographical narratives. Your systematic approach guides them through reconstructing key life events with full contextual dimensions—pinpointing temporal/spatial markers (when/where), central characters, causal chains, and emotional transformations. Using a 'beginning-development-turning point' story structure, you'll elicit rich details through nuanced questioning: 'What was your life circumstance before this event? What served as the catalyst? What decisive moments emerged during the process? How did your understanding evolve afterward?' By employing emotional arc tracking ('If this experience were weather patterns, what sequence would it follow?') and multi-perspective reflection ('How would your present self reinterpret that scene?'), you'll reveal both factual sequences and inner growth trajectories. Your toolkit includes sensory activation ('What distinctive sounds or scents defined that space?') for enhanced recall and gap analysis ('You mentioned A then jumped to C—what connected these moments?') to ensure narrative cohesion. The process yields three integrated biography components: a chronological fact timeline, psychological journey mapping, and distilled life lessons. Throughout, you maintain narrative ethics with regular comfort checks ('Shall we approach this sensitive topic differently?') and empower reframing choices ('Would you categorize this story as rebirth or fateful twist?'). Now, where shall we begin your life exploration? Key career crossroads, profound relationship chapters, or transformative identity journeys—which domain calls to you first? Make your response short and it is better to have two or three sentences maximum."
                })

            print(f"Sending request to AI API...")
            response = requests.post(
                'https://open.bigmodel.cn/api/paas/v4/chat/completions',
                json={
                    'model': 'glm-4-Plus',
                    'messages': messages
                },
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {Config.CHAT_API_KEY}'
                },
                timeout=30  # 添加超时设置
            )
            
            print(f"API Response status: {response.status_code}")
            response_data = response.json()
            
            if not response.ok:
                print(f"API Error response: {response_data}")
                raise Exception(f"API Error {response.status_code}: {response_data.get('error', 'Unknown error')}")
            
            if 'choices' not in response_data or not response_data['choices']:
                print(f"Invalid response format: {response_data}")
                raise Exception("No response from AI model")
                
            print("Chat request successful")
            return response_data
        except requests.exceptions.Timeout:
            print("Request timeout error")
            raise Exception("Request timeout - please try again")
        except requests.exceptions.ConnectionError:
            print("Connection error")
            raise Exception("Network connection error - please check your internet connection")
        except requests.exceptions.RequestException as e:
            print(f"Request error: {str(e)}")
            raise Exception(f"Network error: {str(e)}")
        except Exception as e:
            print(f"Chat error: {str(e)}")
            raise Exception(f"Failed to process chat: {str(e)}")

class ConversationService:
    @staticmethod
    def create_conversation(title, content, date, messages=None):
        try:
            conversation = Conversation(title=title, content=content, date=date)
            db.session.add(conversation)
            db.session.commit()

            if messages:
                for message in messages:
                    chat_message = ChatMessage(
                        conversation_id=conversation.id,
                        role=message['role'],
                        content=message['content']
                    )
                    db.session.add(chat_message)
                db.session.commit()

            return conversation
        except Exception as e:
            db.session.rollback()
            raise Exception(f"Failed to create conversation: {str(e)}")

    @staticmethod
    def get_all_conversations():
        try:
            return Conversation.query.all()
        except Exception as e:
            raise Exception(f"Failed to fetch conversations: {str(e)}")

    @staticmethod
    def get_conversation(conversation_id):
        try:
            return Conversation.query.get(conversation_id)
        except Exception as e:
            raise Exception(f"Failed to fetch conversation: {str(e)}")

    @staticmethod
    def save_messages(conversation_id, messages):
        try:
            for message in messages:
                # Only save user messages
                if message['role'] == 'user':
                    chat_message = ChatMessage(
                        conversation_id=conversation_id,
                        role=message['role'],
                        content=message['content']
                    )
                    db.session.add(chat_message)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            raise Exception(f"Failed to save messages: {str(e)}") 