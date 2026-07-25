from flask import Flask, request, jsonify, render_template, Response, stream_with_context
import json
from flask_cors import CORS
from models import db, Message
from config import Config
from utils import token_manager, summarizer, context_builder
from utils import file_processor
import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__, 
            template_folder=os.path.join(BASE_DIR, 'templates'),
            static_folder=os.path.join(BASE_DIR, 'static'))
app.config.from_object(Config)
CORS(app)

db.init_app(app)

with app.app_context():
    db.create_all()

@app.route('/')
def index():
    # Archive all messages on index load to start a fresh chat
    Message.query.update({Message.is_archived: True})
    db.session.commit()
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    user_message_text = data.get('message', '').strip()
    
    if not user_message_text:
        return jsonify({"error": "Message cannot be empty"}), 400
    
    def generate():
        try:
            with app.app_context():
                # 1. Save user message
                user_tokens = token_manager.estimate_tokens(user_message_text)
                user_msg = Message(role="user", content=user_message_text, token_count=user_tokens)
                db.session.add(user_msg)
                db.session.commit()
                
                # 2. Build context
                all_messages = Message.query.filter_by(is_archived=False).order_by(Message.timestamp.asc()).all()
                context = context_builder.build_context(all_messages)
                
                # 3. Stream from Groq
                accumulated_response = []
                for chunk in summarizer.call_groq_stream(context):
                    accumulated_response.append(chunk)
                    yield f"data: {chunk}\n\n"
                
                full_text = "".join(accumulated_response)
                
                # 4. Save assistant response
                assistant_tokens = token_manager.estimate_tokens(full_text)
                assistant_msg = Message(role="assistant", content=full_text, token_count=assistant_tokens)
                db.session.add(assistant_msg)
                db.session.commit()
                
                # 5. Get updated stats and send final chunk
                all_messages_updated = Message.query.filter_by(is_archived=False).order_by(Message.timestamp.asc()).all()
                stats = token_manager.get_token_stats(all_messages_updated)
                
                yield f"data: [STATS]{json.dumps(stats)}\n\n"
                
        except Exception as e:
            yield f"data: [ERROR]{str(e)}\n\n"

    return Response(stream_with_context(generate()), mimetype='text/event-stream')

@app.route('/summarize', methods=['POST'])
def summarize():
    try:
        # 1. Fetch all active non-pinned messages
        to_summarize = Message.query.filter_by(is_archived=False, is_pinned=False).order_by(Message.timestamp.asc()).all()
        
        if len(to_summarize) < 2:
            return jsonify({"message": "Not enough messages to summarize (need at least one exchange)"}), 200
        
        # 2. Call summarizer
        summary_text = summarizer.summarize_messages(to_summarize)
        summary_content = f"[SUMMARY] {summary_text}"
        
        # 3. Archive the summarized messages
        for msg in to_summarize:
            msg.is_archived = True
        
        # 4. Save summary as system message
        summary_tokens = token_manager.estimate_tokens(summary_content)
        summary_msg = Message(role="system", content=summary_content, token_count=summary_tokens)
        db.session.add(summary_msg)
        db.session.commit()
        
        return jsonify({
            "message": f"Successfully summarized the entire conversation ({len(to_summarize)} messages).",
            "summary": summary_content
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/prune', methods=['POST'])
def prune():
    try:
        all_active = Message.query.filter_by(is_archived=False, is_pinned=False).order_by(Message.timestamp.asc()).all()
        if len(all_active) <= 6:
            return jsonify({"message": "No messages to prune beyond the 6 most recent"}), 200
        
        to_prune = all_active[:-6]
        count = len(to_prune)
        for msg in to_prune:
            msg.is_archived = True
        db.session.commit()
        
        return jsonify({"message": f"Pruned {count} messages"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/messages', methods=['GET'])
def get_messages():
    active_messages = Message.query.filter_by(is_archived=False).order_by(Message.timestamp.asc()).all()
    stats = token_manager.get_token_stats(active_messages)
    return jsonify({
        "messages": [m.to_dict() for m in active_messages],
        "token_stats": stats
    })

@app.route('/message/<int:id>', methods=['DELETE'])
def delete_message(id):
    msg = Message.query.get(id)
    if not msg:
        return jsonify({"error": "Message not found"}), 404
    
    msg.is_archived = True
    deleted_count = 1

    # Cascading deletion: if user message is deleted, archive the next assistant message
    if msg.role == 'user':
        next_msg = Message.query.filter(
            Message.timestamp > msg.timestamp,
            Message.is_archived == False
        ).order_by(Message.timestamp.asc()).first()
        
        if next_msg and next_msg.role == 'assistant':
            next_msg.is_archived = True
            deleted_count += 1
            
    db.session.commit()
    return jsonify({"message": f"Message{'s' if deleted_count > 1 else ''} deleted"})

@app.route('/pin/<int:id>', methods=['POST'])
def toggle_pin(id):
    msg = Message.query.get(id)
    if not msg:
        return jsonify({"error": "Message not found"}), 404
    
    new_pin_status = not msg.is_pinned
    msg.is_pinned = new_pin_status

    # Cascading pin: if user message is pinned/unpinned, do the same for the next assistant message
    if msg.role == 'user':
        next_msg = Message.query.filter(
            Message.timestamp > msg.timestamp,
            Message.is_archived == False
        ).order_by(Message.timestamp.asc()).first()
        
        if next_msg and next_msg.role == 'assistant':
            next_msg.is_pinned = new_pin_status
            
    db.session.commit()
    return jsonify({"is_pinned": msg.is_pinned})

@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle image or PDF upload, extract content, and get AI response."""
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files['file']
    user_prompt = request.form.get('prompt', '').strip()

    if not file.filename:
        return jsonify({"error": "No file selected"}), 400

    filename = file.filename.lower()
    file_bytes = file.read()
    mime_type = file.content_type or ''

    # Enforce 10 MB limit
    if len(file_bytes) > 10 * 1024 * 1024:
        return jsonify({"error": "File too large. Maximum size is 10 MB."}), 400

    try:
        # --- Determine file type and extract content ---
        # Hard cap: ~6000 chars ≈ 1500 tokens — keeps single uploads from flooding the context
        MAX_CONTENT_CHARS = 6000

        if filename.endswith('.pdf') or mime_type == 'application/pdf':
            extracted_text = file_processor.extract_text_from_pdf(file_bytes)

            # Truncate if too long
            if len(extracted_text) > MAX_CONTENT_CHARS:
                extracted_text = extracted_text[:MAX_CONTENT_CHARS] + \
                    f"\n\n*[...content truncated to {MAX_CONTENT_CHARS} characters to fit context window]*"

            label = f"📄 **PDF Uploaded: {file.filename}**"
            if user_prompt:
                user_message_text = f"{label}\n\n{user_prompt}\n\n---\n*Extracted PDF content:*\n{extracted_text}"
            else:
                user_message_text = f"{label}\n\n---\n*Extracted PDF content:*\n{extracted_text}\n\nPlease analyze the content above."

            # Save as user message and get AI response
            user_tokens = token_manager.estimate_tokens(user_message_text)
            user_msg = Message(role="user", content=user_message_text, token_count=user_tokens)
            db.session.add(user_msg)
            db.session.commit()

            all_messages = Message.query.filter_by(is_archived=False).order_by(Message.timestamp.asc()).all()
            context = context_builder.build_context(all_messages)
            assistant_response = summarizer.call_groq(context)

        elif mime_type.startswith('image/') or any(filename.endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']):
            # Map extension to mime type if not provided
            if not mime_type.startswith('image/'):
                ext_map = {'.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png',
                           '.gif': 'image/gif', '.webp': 'image/webp'}
                for ext, mt in ext_map.items():
                    if filename.endswith(ext):
                        mime_type = mt
                        break

            label = f"🖼️ **Image Uploaded: {file.filename}**"
            prompt_for_vision = user_prompt if user_prompt else ""
            assistant_response = file_processor.analyze_image_with_groq(file_bytes, mime_type, prompt_for_vision)

            # Truncate vision response if unexpectedly large
            if len(assistant_response) > MAX_CONTENT_CHARS:
                assistant_response = assistant_response[:MAX_CONTENT_CHARS] + \
                    "\n\n*[...response truncated to fit context window]*"

            # Store user turn as: label + optional prompt
            if user_prompt:
                user_message_text = f"{label}\n\n{user_prompt}"
            else:
                user_message_text = f"{label}\n\nPlease analyze this image."

            user_tokens = token_manager.estimate_tokens(user_message_text)
            user_msg = Message(role="user", content=user_message_text, token_count=user_tokens)
            db.session.add(user_msg)
            db.session.commit()

        else:
            return jsonify({"error": "Unsupported file type. Please upload an image (JPG, PNG, GIF, WEBP) or a PDF."}), 400

        # Save assistant response
        assistant_tokens = token_manager.estimate_tokens(assistant_response)
        assistant_msg = Message(role="assistant", content=assistant_response, token_count=assistant_tokens)
        db.session.add(assistant_msg)
        db.session.commit()

        all_messages_updated = Message.query.filter_by(is_archived=False).order_by(Message.timestamp.asc()).all()
        stats = token_manager.get_token_stats(all_messages_updated)

        return jsonify({
            "response": assistant_response,
            "token_stats": stats
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/reset', methods=['POST'])
def reset_chat():
    Message.query.update({Message.is_archived: True})
    db.session.commit()
    return jsonify({"message": "Conversation reset"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('FLASK_PORT', 5000)), debug=os.getenv('FLASK_DEBUG', 'true').lower() == 'true')
