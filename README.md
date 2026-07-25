# ContextShift

ContextShift is an intelligent chat application powered by Groq and Flask, designed to handle long conversations through smart context management (summarization, pruning, and pinning).

## Features

- **Real-time Streaming**: Enjoy fast, ChatGPT-style streaming responses using Groq's high-speed inference.
- **Smart Context Management**:
  - **Summarization**: Collapses long chat history into a dense summary to save tokens.
  - **Pruning**: Automatically archives older, less relevant messages to stay within token limits.
  - **Pinning**: Keep important instructions or facts in the active context window indefinitely.
- **File Support**: Upload images for visual analysis or PDFs for text extraction and discussion.
- **Token Tracking**: Real-time visual feedback on your context window usage.
- **Modern UI**: Sleek, glassmorphic dark/light mode interface.

## Tech Stack

- **Backend**: Python, Flask, SQLAlchemy, Groq API.
- **Frontend**: Vanilla JS, HTML, CSS.
- **Processing**: PyPDF2 (PDF), Pillow (Images).

## Getting Started

### Prerequisites

- Python 3.8+
- Groq API Key

### Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/yourusername/ContextShift.git
   cd ContextShift
   ```

2. **Set up a virtual environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure Environment Variables**:
   Copy the example environment file and add your keys:
   ```bash
   cp .env.example .env
   ```
   Edit `.env` and add your `GROQ_API_KEY`.

5. **Run the application**:
   ```bash
   python app.py
   ```
   Open `http://localhost:5000` in your browser.

## Security Note

This repository uses a `.gitignore` file to ensure that your `.env` file (containing sensitive API keys) and local database files are never uploaded to GitHub. Always keep your `.env` file private.

## License

MIT
