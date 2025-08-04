from flask import Blueprint, request, jsonify, send_file
from flask_jwt_extended import jwt_required, get_jwt_identity, decode_token
from server_flask.app.blueprints.chat import AIService
from server_flask.app.blueprints.asr import ASRService
from server_flask.app.blueprints.tts import TTSService
# from app.blueprints.openai import AIService
from app.extension import db
from app.models import UserModel, Conversation, ChatMessage, CommunityPost
from io import BytesIO
import requests
from app.config import Config
import os
import tempfile
from datetime import datetime

bp = Blueprint('main', __name__)
ai_service = AIService()
asr_service = ASRService()
tts_service = TTSService()

# Protected routes
@bp.route('/conversations', methods=['POST'])
@jwt_required()
def create_conversation():
    """
    Create a new conversation
    """
    current_user_id = get_jwt_identity()
    data = request.get_json()
    
    try:
        conversation = Conversation(
            user_id=current_user_id,
            title=data['title'],
            content=data['content'],
            date=data['date']
        )
        
        db.session.add(conversation)
        db.session.commit()
        
        # Add initial messages if provided
        if 'messages' in data:
            for msg in data['messages']:
                message = ChatMessage(
                    conversation_id=conversation.id,
                    role=msg['role'],
                    content=msg['content']
                )
                db.session.add(message)
            db.session.commit()
        
        return jsonify(conversation.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': 'Server error'}), 500

@bp.route('/conversations', methods=['GET'])
@jwt_required()
def get_conversations():
    """
    Get all conversations for current user
    """
    current_user_id = get_jwt_identity()
    conversations = Conversation.query.filter_by(user_id=current_user_id).order_by(Conversation.created_at.desc()).all()
    return jsonify([conv.to_dict() for conv in conversations])

@bp.route('/conversations/<int:conversation_id>', methods=['GET'])
@jwt_required()
def get_conversation(conversation_id):
    """
    Get a specific conversation
    """
    current_user_id = get_jwt_identity()
    conversation = Conversation.query.filter_by(id=conversation_id, user_id=current_user_id).first_or_404()
    return jsonify(conversation.to_dict())

@bp.route('/conversations/<int:conversation_id>', methods=['PUT'])
@jwt_required()
def update_conversation(conversation_id):
    """
    Update a conversation
    """
    current_user_id = get_jwt_identity()
    conversation = Conversation.query.filter_by(id=conversation_id, user_id=current_user_id).first_or_404()
    
    data = request.get_json()
    
    try:
        if 'title' in data:
            conversation.title = data['title']
        if 'content' in data:
            conversation.content = data['content']
        if 'date' in data:
            conversation.date = data['date']
        
        db.session.commit()
        return jsonify(conversation.to_dict())
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': 'Server error'}), 500

@bp.route('/conversations/<int:conversation_id>', methods=['DELETE'])
@jwt_required()
def delete_conversation(conversation_id):
    """
    Delete a conversation
    """
    current_user_id = get_jwt_identity()
    conversation = Conversation.query.filter_by(id=conversation_id, user_id=current_user_id).first_or_404()
    
    try:
        db.session.delete(conversation)
        db.session.commit()
        return jsonify({'message': 'Conversation deleted successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': 'Server error'}), 500

@bp.route('/chat', methods=['POST'])
@jwt_required()
def chat():
    """
    Chat with AI and optionally return audio response
    """
    current_user_id = get_jwt_identity()
    data = request.get_json()
    
    try:
        response = ai_service.chat(data['messages'])
        
        # 检查是否需要语音回复
        if data.get('voice_response', False):
            try:
                ai_message_content = response['choices'][0]['message']['content']
                print(f"Generating TTS for: {ai_message_content[:50]}...")  # 调试日志
                
                audio_path = tts_service.text_to_speech_sync(ai_message_content)
                print(f"Generated audio file: {audio_path}")  # 调试日志
                
                # 将音频文件路径添加到响应中 (传递完整路径)
                response['audio_path'] = audio_path
                response['has_audio'] = True
                print("TTS generation successful")  # 调试日志
            except Exception as tts_error:
                print(f"TTS Error: {tts_error}")
                response['has_audio'] = False
                response['tts_error'] = str(tts_error)
        
        return jsonify(response)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/transcribe', methods=['POST'])
@jwt_required()
def transcribe():
    """
    Transcribe audio to text
    """
    if 'audio' not in request.files:
        return jsonify({'error': 'No audio file provided'}), 400
    
    audio_file = request.files['audio']
    try:
        # Convert the audio file to a format that ASRService can process
        audio_data = audio_file.read()
        audio_buffer = BytesIO(audio_data)
        
        # Use the ASR model to transcribe
        res = asr_service.model.generate(
            input=audio_buffer,
            cache={},
            language="auto",
            use_itn=True,
            batch_size_s=60,
            merge_vad=True,
            merge_length_s=15,
        )
        
        # Process result
        from funasr.utils.postprocess_utils import rich_transcription_postprocess
        text = rich_transcription_postprocess(res[0]["text"])
        return jsonify({'text': text.strip()})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/asr/start', methods=['POST'])
@jwt_required()
def start_asr():
    """
    Start ASR recording
    """
    try:
        result = asr_service.start_recording()
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/asr/stop', methods=['POST'])
@jwt_required()
def stop_asr():
    """
    Stop ASR recording
    """
    try:
        result = asr_service.stop_recording()
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/regenerate-text', methods=['POST'])
@jwt_required()
def regenerate_text():
    """
    Regenerate text using AI
    """
    try:
        data = request.get_json()
        if not data or 'text' not in data:
            return jsonify({'error': 'No text provided'}), 400

        current_content = data.get('currentContent', '')
        new_content = data['text']
        
        regenerated_text = ai_service.regenerate_text(current_content, new_content)
        return jsonify({'regenerated_text': regenerated_text})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/audio/<path:filename>', methods=['GET'])
def get_audio(filename):
    """
    Serve audio files with token authentication
    """
    try:
        # 支持两种认证方式：Header中的Authorization或查询参数中的token
        token = None
        
        # 从Authorization header获取token
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
        
        # 从查询参数获取token
        if not token:
            token = request.args.get('token')
        
        if not token:
            return jsonify({'error': 'No token provided'}), 401
        
        # 验证token
        try:
            # 手动验证token
            decoded_token = decode_token(token)
            current_user_id = decoded_token['sub']
            print(f"Audio request authenticated for user: {current_user_id}")
        except Exception as jwt_error:
            print(f"JWT verification failed: {jwt_error}")
            return jsonify({'error': 'Invalid token'}), 401
        
        print(f"Audio request for: {filename}")  # 调试日志
        
        # 处理Windows路径分隔符
        if filename.startswith('C:\\'):
            audio_path = filename
        else:
            # 如果不是完整路径，假设是临时文件名
            audio_path = filename
        
        print(f"Resolved audio path: {audio_path}")  # 调试日志
        
        if not os.path.exists(audio_path):
            print(f"Audio file not found: {audio_path}")  # 调试日志
            return jsonify({'error': 'File not found'}), 404
        
        print(f"Serving audio file: {audio_path}")  # 调试日志
        
        # 返回音频文件
        return send_file(
            audio_path,
            mimetype='audio/mpeg',
            as_attachment=False,
            download_name=f'tts_audio_{os.path.basename(audio_path)}'
        )
    except Exception as e:
        print(f"Error serving audio: {str(e)}")  # 调试日志
        return jsonify({'error': str(e)}), 500

@bp.route('/tts/voices', methods=['GET'])
@jwt_required()
def get_tts_voices():
    """
    Get available TTS voices
    """
    try:
        voices = TTSService.get_available_voices()
        return jsonify({'voices': voices})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Community API endpoints
@bp.route('/community/posts', methods=['GET'])
@jwt_required()
def get_community_posts():
    """
    Get all public community posts
    """
    try:
        posts = CommunityPost.query.filter_by(is_public=True).order_by(CommunityPost.created_at.desc()).all()
        return jsonify({
            'success': True,
            'posts': [post.to_dict() for post in posts]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/community/my-posts', methods=['GET'])
@jwt_required()
def get_my_posts():
    """
    Get current user's community posts
    """
    current_user_id = get_jwt_identity()
    try:
        posts = CommunityPost.query.filter_by(user_id=current_user_id).order_by(CommunityPost.created_at.desc()).all()
        return jsonify({
            'success': True,
            'posts': [post.to_dict() for post in posts]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/community/posts', methods=['POST'])
@jwt_required()
def create_community_post():
    """
    Create a new community post
    """
    current_user_id = get_jwt_identity()
    data = request.get_json()
    
    if not data or not data.get('title') or not data.get('content'):
        return jsonify({'error': 'Title and content are required'}), 400
    
    try:
        post = CommunityPost(
            user_id=current_user_id,
            title=data['title'],
            content=data['content'],
            is_public=data.get('isPublic', True),
            source_type=data.get('sourceType', 'original'),
            source_id=data.get('sourceId')
        )
        
        db.session.add(post)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'post': post.to_dict()
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@bp.route('/community/posts/<int:post_id>', methods=['DELETE'])
@jwt_required()
def delete_community_post(post_id):
    """
    Delete a community post (only by the author)
    """
    current_user_id = get_jwt_identity()
    
    try:
        post = CommunityPost.query.filter_by(id=post_id, user_id=current_user_id).first()
        if not post:
            return jsonify({'error': 'Post not found or unauthorized'}), 404
        
        db.session.delete(post)
        db.session.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

