# AI-Powered MUD Game

A multiplayer text-based adventure game powered by AI, featuring real-time visuals, freeform interactions, and persistent AI NPCs.

## Features

- Real-time multiplayer interaction
- AI-powered NPCs with persistent memory
- Dynamic world generation
- Real-time image generation for scenes
- Chat and emote system
- Persistent world state

## Tech Stack

### Backend

- FastAPI (Python)
- Redis for state management
- ChromaDB for vector storage
- OpenAI GPT-4 for text generation
- DALL-E 3 for image generation
- WebSocket for real-time communication

### Frontend

- Next.js 14
- TypeScript
- Tailwind CSS
- Socket.io for WebSocket communication
- Zustand for state management

## Setup

1. Clone the repository:

   ```bash
   git clone <repository-url>
   cd worlds
   ```

2. Set up the backend:

   ```bash
   cd server
   python -m venv .venv
   source .venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. Create a `.env` file in the `server` directory:

   ```
   OPENAI_API_KEY=your_openai_api_key
   REDIS_URL=redis://localhost:6379
   SECRET_KEY=your_secret_key
   DEBUG=True
   ```

4. Set up the frontend:

   ```bash
   cd ../client
   npm install
   ```

5. Create a `.env.local` file in the `client` directory:

   ```
   NEXT_PUBLIC_API_URL=http://localhost:8000
   ```

6. Start Redis:

   ```bash
   redis-server
   ```

7. Start the backend server:

   ```bash
   cd server
   uvicorn app.main:app --reload
   ```

8. Start the frontend development server:

   ```bash
   cd client
   npm run dev
   ```

9. Open your browser and navigate to `http://localhost:3000`

## Game Commands

- Regular text input: Interpreted as game actions
- `/chat [message]`: Send a chat message to other players in the room
- Type with emote mode enabled: Perform an emote action

## Development

### Backend Structure

- `server/app/main.py`: Main FastAPI application
- `server/app/models.py`: Pydantic models
- `server/app/database.py`: Database interactions
- `server/app/ai_handler.py`: AI integration
- `server/app/game_manager.py`: Game logic

### Frontend Structure

- `client/src/components/`: React components
- `client/src/services/`: API and WebSocket services
- `client/src/store/`: Zustand state management
- `client/src/types/`: TypeScript types

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

MIT License
