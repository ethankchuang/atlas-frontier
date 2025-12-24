<div align="center">

![Atlas Frontier Banner](assets/atlas_frontier_banner.png)

# **ATLAS FRONTIER**

### *An AI-Powered Multiplayer Adventure*

[![Next.js](https://img.shields.io/badge/Next.js-14-black)](https://nextjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-Python-009688)](https://fastapi.tiangolo.com/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.0-blue)](https://www.typescriptlang.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**A groundbreaking multiplayer text-based adventure game where AI breathes life into every interaction, creating a dynamic, ever-evolving world of limitless possibilities.**

[Get Started](#-getting-started) • [Features](#-features) • [Tech Stack](#-tech-stack) • [Documentation](#-documentation)

</div>

---

## 🌟 Features

### Immersive AI-Driven Gameplay
- **Intelligent NPCs** - Interact with AI-powered characters that remember your conversations and relationships
- **Dynamic World Generation** - Explore a living world that evolves and responds to player actions
- **Freeform Interactions** - Express yourself naturally; the AI understands and responds to creative commands

### Real-Time Multiplayer
- **Seamless Collaboration** - Adventure alongside other players in real-time
- **Rich Communication** - Chat system with emotes and expressive actions
- **Persistent World State** - Your actions and achievements persist across sessions

### Visual Storytelling
- **AI-Generated Scenes** - Every location comes alive with unique, dynamically generated imagery
- **Atmospheric Immersion** - Visual representations enhance the narrative experience

### Advanced Game Systems
- **Quest System** - Engage in dynamically generated quests with meaningful rewards
- **Combat Mechanics** - Strategic turn-based combat with monsters and creatures
- **Inventory Management** - Collect, manage, and use items throughout your journey
- **Biome Diversity** - Explore varied environments, each with unique characteristics

---

## 🚀 Getting Started

### Prerequisites

Before you begin, ensure you have the following installed:
- **Node.js** (v18 or higher)
- **Python** (v3.11 or higher)
- **Redis** (v7.0 or higher)
- **OpenAI API Key** ([Get one here](https://platform.openai.com/api-keys))
- **Replicate API Token** ([Get one here](https://replicate.com/account/api-tokens))
- **Supabase Project** ([Create one here](https://supabase.com/dashboard))

### Installation

#### 1. Clone the Repository

```bash
git clone <repository-url>
cd worlds
```

#### 2. Backend Setup

```bash
cd server
python -m venv .venv

# Activate virtual environment
# On macOS/Linux:
source .venv/bin/activate
# On Windows:
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

#### 3. Backend Environment Configuration

Create a `.env` file in the `server` directory:

```env
# AI Services
OPENAI_API_KEY=your_openai_api_key_here
REPLICATE_API_TOKEN=your_replicate_api_token_here

# Database
REDIS_URL=redis://localhost:6379
SUPABASE_URL=your_supabase_project_url
SUPABASE_ANON_KEY=your_supabase_anon_key
SUPABASE_SERVICE_ROLE_KEY=your_supabase_service_role_key

# Image Generation
IMAGE_GENERATION_ENABLED=True
IMAGE_PROVIDER=replicate

# Security
SECRET_KEY=your_secret_key_here
DEBUG=True
```

> **Note:**
> - Get your OpenAI API key from the [OpenAI Platform](https://platform.openai.com/api-keys)
> - Get your Replicate API token from [Replicate Settings](https://replicate.com/account/api-tokens)
> - Get your Supabase credentials from your [Supabase Dashboard](https://supabase.com/dashboard) under Project Settings > API
> - Generate a secure random string for `SECRET_KEY` (e.g., `openssl rand -hex 32`)

#### 4. Frontend Setup

```bash
cd ../client
npm install
```

#### 5. Frontend Environment Configuration

Create a `.env.local` file in the `client` directory:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### Running Atlas Frontier

#### Start Redis Server

```bash
redis-server
```

Keep this terminal running.

#### Start the Backend Server

Open a new terminal:

```bash
cd server
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uvicorn app.main:app --reload
```

The backend API will be available at `http://localhost:8000`

#### Start the Frontend Development Server

Open another terminal:

```bash
cd client
npm run dev
```

#### Access the Game

Open your browser and navigate to:
```
http://localhost:3000
```

**You're ready to explore Atlas Frontier!**

---

## 🎮 Gameplay Guide

### Commands & Interactions

**Natural Actions**
- Simply type what you want to do: `go north`, `examine the ancient tome`, `talk to the merchant`
- The AI interprets your intent and responds dynamically

**Chat Commands**
- `/chat [message]` - Communicate with other players in your location
- Example: `/chat Hello, fellow adventurers!`

**Emote System**
- Enable emote mode to perform expressive actions
- Example: `*waves enthusiastically*`, `*examines the mysterious artifact carefully*`

**Movement**
- Navigate using cardinal directions: `north`, `south`, `east`, `west`, `up`, `down`
- Or simply: `n`, `s`, `e`, `w`, `u`, `d`

**Combat**
- `attack [target]` - Engage in combat with creatures
- `retreat` - Attempt to flee from combat
- `use [item]` - Use an item during combat

**Inventory**
- `inventory` or `i` - View your possessions
- `take [item]` - Pick up an item
- `drop [item]` - Remove an item from your inventory

---

## 🛠 Tech Stack

### Backend Architecture

| Technology | Purpose |
|------------|---------|
| **FastAPI** | High-performance Python web framework |
| **Supabase (PostgreSQL)** | Primary database for persistent game data |
| **Supabase Storage** | Permanent image storage with CDN delivery |
| **Redis** | Real-time state management and caching |
| **ChromaDB** | Vector storage for AI memory and context |
| **OpenAI GPT-4.1 Nano** | Natural language processing and game narration |
| **Flux 1.1 Pro Ultra** | AI image generation via Replicate API |
| **WebSocket** | Real-time bidirectional communication |
| **Pydantic** | Data validation and settings management |

### Frontend Architecture

| Technology | Purpose |
|------------|---------|
| **Next.js 14** | React framework with server-side rendering |
| **TypeScript** | Type-safe JavaScript for robust development |
| **Tailwind CSS** | Utility-first styling framework |
| **Socket.io** | Real-time WebSocket communication |
| **Zustand** | Lightweight state management |
| **React Hooks** | Modern component logic |

---

## 📁 Project Structure

### Backend (`/server`)

```
server/
├── app/
│   ├── main.py              # FastAPI application entry point
│   ├── models.py            # Pydantic data models
│   ├── database.py          # Redis and database interactions
│   ├── ai_handler.py        # OpenAI integration and AI logic
│   ├── game_manager.py      # Core game mechanics
│   ├── quest_manager.py     # Quest system logic
│   ├── combat_manager.py    # Combat mechanics
│   └── biome_manager.py     # Biome and environment management
├── requirements.txt         # Python dependencies
└── .env                     # Environment variables (create this)
```

### Frontend (`/client`)

```
client/
├── src/
│   ├── app/                 # Next.js app directory
│   ├── components/          # React components
│   │   ├── GameInterface.tsx
│   │   ├── ChatPanel.tsx
│   │   └── ImageDisplay.tsx
│   ├── services/            # API and WebSocket services
│   │   ├── api.ts
│   │   └── socket.ts
│   ├── store/               # Zustand state management
│   └── types/               # TypeScript type definitions
├── public/                  # Static assets
├── package.json             # Node dependencies
└── .env.local               # Environment variables (create this)
```

---

## 🔧 Development

### Running Tests

```bash
# Backend tests
cd server
pytest

# Frontend tests
cd client
npm test
```

### Code Quality

```bash
# Backend linting
cd server
pylint app/

# Frontend linting
cd client
npm run lint
```

### Building for Production

```bash
# Build frontend
cd client
npm run build

# Start production server
npm start
```

---

## 📚 Documentation

Comprehensive documentation for specific systems:

- [Quest System Implementation](QUEST_SYSTEM_FINAL_DOCUMENTATION.md)
- [Quest Integration Guide](QUEST_INTEGRATION_GUIDE.md)
- [Monster Combat System](MONSTER_SYSTEM_IMPLEMENTATION.md)
- [Dynamic Validation System](DYNAMIC_VALIDATION_SYSTEM.md)
- [API Key Setup Guide](API_KEY_SETUP.md)
- [Image Retry System](IMAGE_RETRY_SYSTEM.md)

---

## 🤝 Contributing

We welcome contributions to Atlas Frontier! Here's how to get started:

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **Commit** your changes (`git commit -m 'Add amazing feature'`)
4. **Push** to the branch (`git push origin feature/amazing-feature`)
5. **Open** a Pull Request

Please ensure your code follows our style guidelines and includes appropriate tests.

---

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- Powered by OpenAI's GPT-4.1 Nano for intelligent narrative generation
- Image generation by Black Forest Labs' Flux 1.1 Pro Ultra via Replicate
- Data persistence by Supabase (PostgreSQL + Storage)
- Built with modern web technologies
- Inspired by classic MUD games and modern AI capabilities

---

<div align="center">

**Ready to embark on your adventure?**

[Start Playing](#-getting-started) • [Report Issues](https://github.com/your-repo/issues) • [Join Discussion](https://github.com/your-repo/discussions)

---

*Built with ❤️ by the Atlas Frontier team*

</div>
