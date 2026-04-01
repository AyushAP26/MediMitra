# MediMitra

MediMitra (Medical Friend) is an AI-powered healthcare chatbot application built with Flask and MongoDB. It utilizes the Groq API for lightning-fast language model capabilities to provide health tips, disease diagnosis, and first aid instructions in an accessible format.

## Features

- **AI Health Assistant:** An intelligent chatbot interface to answer health and medical queries.
- **Disease & Symptom Detection:** Smart intent classification that routes questions to specialized disease cards or general health tip responses.
- **First Aid Guidance:** Step-by-step numbered treatment instructions.
- **Rate Limiting:** Protects the chat endpoint from abuse (configured to 30 requests/minute per IP).
- **Responsive UI:** Modern, dynamic card-based interface with micro-animations.

## Tech Stack

- **Backend:** Python, Flask Frameowrk
- **Database:** MongoDB (`pymongo`)
- **AI Integration:** Groq API (leveraging faster inference via `openai` python SDK)
- **Language Processing:** `langdetect`
- **Frontend:** HTML, CSS, JavaScript

## Setup Instructions

### 1. Prerequisites
Ensure you have the following installed on your local machine:
- [Python 3.8+](https://www.python.org/downloads/)
- [MongoDB](https://www.mongodb.com/try/download/community) (running locally or via MongoDB Atlas)
- A [Groq API Key](https://console.groq.com/keys)

### 2. Clone the Repository
```bash
git clone https://github.com/AyushAP26/MediMitra.git
cd MediMitra
```

### 3. Setup Virtual Environment
```bash
python -m venv venv

# On Windows:
venv\Scripts\activate

# On macOS/Linux:
source venv/bin/activate
```

### 4. Install Dependencies
```bash
pip install -r requirements.txt
```

### 5. Environment Variables
Create a `.env` file in the root of your project directory and add the necessary configuration:

```env
# Database Configuration
MONGO_URI="mongodb://localhost:27017/"
DB_NAME="medimitra"

# Server Configuration
PORT=5000
FLASK_DEBUG="true"

# API Keys
GROQ_API_KEY="your_groq_api_key_here"
```

### 6. Run the Application
```bash
python app.py
```
After starting the server, open your web browser and navigate to `http://localhost:5000` to interact with MediMitra.

## Project Structure
- `app.py`: Main application entry point and Flask setup.
- `config.py`: Environment variables and logger configuration.
- `routes/`: Blueprint definitions for API endpoints.
- `services/`: Core logic containing intent classification and symptom detection.
- `utils/`: Helper functions.
- `tests/`: Automated unit tests.
- `templates/` & `static/`: Frontend HTML files and static assets (CSS, JS).
