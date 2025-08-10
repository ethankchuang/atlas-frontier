# AI MUD Coding Agent Flow Guide

## 🎯 Objective

You are an AI coding assistant helping build an AI-powered multiplayer MUD (multi-user dungeon) with real-time visuals, freeform interactions, and persistent AI NPCs.

Use the following spec as the authoritative reference:

Spec is in the file: "game_spec.md"

---

## 🛠️ Step-by-Step Build Plan

### ✅ STEP 1: Project Setup

- Scaffold a monorepo with:
  - `client/` → Next.js + Tailwind app
  - `server/` → FastAPI backend with async support
  - `shared/` → Types and constants (optional)

### ✅ STEP 2: Backend Architecture

**Directory**: `server/`

- Create `main.py` using FastAPI
- Setup REST endpoints:
  - `POST /action`
  - `POST /generate_image`
  - `GET /room/{id}`
  - `POST /presence`
  - `POST /chat`
  - `POST /npc`
- Setup persistent memory (e.g., Redis or Firestore)
- Connect to:
  - OpenAI GPT-4o API (chat + image)
  - Pinecone or Chroma (NPC memory vector store)

### ✅ STEP 3: World Graph and Models

- Define Room model (ID, title, description, NPCs, players)
- Create data storage format (JSON, Redis, or Firestore)
- Implement world generation logic on `/start`

### ✅ STEP 4: NPC System

- Each NPC has:
  - A persistent memory store (vector + structured logs)
  - Behavior controlled by LLM prompt injection
- Endpoint `/npc` handles interaction + memory updates

### ✅ STEP 5: Frontend Architecture

**Directory**: `client/`

- Fullscreen layout
  - Image display (`<img>` or `<canvas>`)
  - Text scroll area (chat-style)
  - Input box for commands
  - Avatar/emote overlay (top corner)
- Use WebSocket to update room presence/chat
- Display streamed text messages from server

### ✅ STEP 6: Prompt Templates

- Game Master prompt: handles world logic
- NPC prompt: scoped memory + recent dialog context

---

## 🔧 Technical Stack

- **Frontend**: React (Next.js), TailwindCSS, Socket.io
- **Backend**: FastAPI, Uvicorn, Redis/Firestore
- **Memory**: Pinecone, ChromaDB, or LangChain vector tools
- **LLM & Image**: OpenAI GPT-4o (for both text and image)
- **Optional Dev Tools**: Docker, GitHub Actions

---

## 📋 Goals for the AI Coding Agent

You should:

- Generate each file step by step, starting with the backend.
- Always output complete files when writing code (not partial snippets).
- Include TODO comments where future extension is needed.
- Run schema checks where appropriate.
- Add test scripts if possible.

---

## ✅ Initial Output Instructions

Start by creating:

- A file `main.py` in the `server/` folder with FastAPI and Uvicorn setup.
- A base world model (e.g., Room, Player, NPC).
- Then continue to build the `/action` and `/room/{id}` endpoints.
