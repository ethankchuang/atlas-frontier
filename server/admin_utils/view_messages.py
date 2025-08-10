#!/usr/bin/env python3
"""
Admin utility to view all stored message data
Usage: python view_messages.py [--type action|chat|session|all] [--player PLAYER_ID] [--room ROOM_ID] [--limit N]
"""

import asyncio
import sys
import os
import json
import argparse
from datetime import datetime
from typing import Dict, List, Optional

# Add the server directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.database import Database
from app.models import ActionRecord, ChatMessage

class MessageViewer:
    def __init__(self):
        self.db = Database()
    
    async def view_action_records(self, player_id: Optional[str] = None, room_id: Optional[str] = None, limit: int = 50):
        """View stored action records"""
        print("🎮 ACTION RECORDS")
        print("=" * 80)
        
        try:
            # Get all action records
            records = await self.db.get_action_history(player_id, room_id, limit)
            
            if not records:
                print("❌ No action records found")
                return
            
            print(f"📊 Found {len(records)} action records")
            print()
            
            for i, record in enumerate(records, 1):
                print(f"📝 Record #{i}")
                print(f"   ID: {record['id']}")
                print(f"   Player: {record['player_id']}")
                print(f"   Room: {record['room_id']}")
                print(f"   Session: {record['session_id']}")
                print(f"   Timestamp: {record['timestamp']}")
                print(f"   Action: {record['action'][:100]}{'...' if len(record['action']) > 100 else ''}")
                print(f"   AI Response: {record['ai_response'][:100]}{'...' if len(record['ai_response']) > 100 else ''}")
                
                if record.get('metadata'):
                    print(f"   Metadata: {json.dumps(record['metadata'], indent=2)}")
                
                if record.get('updates'):
                    print(f"   Updates: {json.dumps(record['updates'], indent=2)}")
                
                print("-" * 80)
                
        except Exception as e:
            print(f"❌ Error viewing action records: {str(e)}")
    
    async def view_chat_messages(self, player_id: Optional[str] = None, room_id: Optional[str] = None, limit: int = 50):
        """View stored chat messages"""
        print("💬 CHAT MESSAGES")
        print("=" * 80)
        
        try:
            # Get all chat messages
            messages = await self.db.get_chat_history(player_id, room_id, limit)
            
            if not messages:
                print("❌ No chat messages found")
                return
            
            print(f"📊 Found {len(messages)} chat messages")
            print()
            
            for i, message in enumerate(messages, 1):
                print(f"💬 Message #{i}")
                print(f"   ID: {message['id']}")
                print(f"   Player: {message['player_id']}")
                print(f"   Room: {message['room_id']}")
                print(f"   Type: {message['message_type']}")
                print(f"   Timestamp: {message['timestamp']}")
                print(f"   Message: {message['message']}")
                
                if message.get('metadata'):
                    print(f"   Metadata: {json.dumps(message['metadata'], indent=2)}")
                
                print("-" * 80)
                
        except Exception as e:
            print(f"❌ Error viewing chat messages: {str(e)}")
    
    async def view_game_sessions(self, player_id: Optional[str] = None, limit: int = 50):
        """View game sessions"""
        print("🎯 GAME SESSIONS")
        print("=" * 80)
        
        try:
            # Get all sessions
            sessions = await self.db.get_game_sessions(player_id, limit)
            
            if not sessions:
                print("❌ No game sessions found")
                return
            
            print(f"📊 Found {len(sessions)} game sessions")
            print()
            
            for i, session in enumerate(sessions, 1):
                print(f"🎯 Session #{i}")
                print(f"   Session ID: {session['session_id']}")
                print(f"   Player: {session['player_id']}")
                print(f"   Start Time: {session['start_time']}")
                print(f"   Total Actions: {session['total_actions']}")
                print(f"   Rooms Visited: {session.get('rooms_visited', [])}")
                print(f"   Items Obtained: {session.get('items_obtained', [])}")
                print("-" * 80)
                
        except Exception as e:
            print(f"❌ Error viewing game sessions: {str(e)}")
    
    async def view_summary(self):
        """View a summary of all stored data"""
        print("📈 DATA SUMMARY")
        print("=" * 80)
        
        try:
            # Get counts
            action_records = await self.db.get_action_history(limit=1000)
            chat_messages = await self.db.get_chat_history(limit=1000)
            sessions = await self.db.get_game_sessions(limit=1000)
            
            print(f"🎮 Action Records: {len(action_records)}")
            print(f"💬 Chat Messages: {len(chat_messages)}")
            print(f"🎯 Game Sessions: {len(sessions)}")
            
            # Get unique players
            action_players = set(record['player_id'] for record in action_records)
            chat_players = set(msg['player_id'] for msg in chat_messages)
            session_players = set(session['player_id'] for session in sessions)
            
            all_players = action_players | chat_players | session_players
            
            print(f"👥 Unique Players: {len(all_players)}")
            print(f"   Action Players: {len(action_players)}")
            print(f"   Chat Players: {len(chat_players)}")
            print(f"   Session Players: {len(session_players)}")
            
            # Get unique rooms
            action_rooms = set(record['room_id'] for record in action_records)
            chat_rooms = set(msg['room_id'] for msg in chat_messages)
            
            all_rooms = action_rooms | chat_rooms
            print(f"🏠 Unique Rooms: {len(all_rooms)}")
            
            # Time range
            if action_records:
                timestamps = [datetime.fromisoformat(record['timestamp']) for record in action_records]
                earliest = min(timestamps)
                latest = max(timestamps)
                print(f"⏰ Time Range: {earliest} to {latest}")
            
            print("-" * 80)
            
        except Exception as e:
            print(f"❌ Error viewing summary: {str(e)}")
    
    async def export_data(self, filename: str = "message_data_export.json"):
        """Export all data to a JSON file"""
        print(f"📤 Exporting data to {filename}")
        print("=" * 80)
        
        try:
            export_data = {
                "export_timestamp": datetime.utcnow().isoformat(),
                "action_records": await self.db.get_action_history(limit=10000),
                "chat_messages": await self.db.get_chat_history(limit=10000),
                "game_sessions": await self.db.get_game_sessions(limit=10000)
            }
            
            with open(filename, 'w') as f:
                json.dump(export_data, f, indent=2, default=str)
            
            print(f"✅ Data exported to {filename}")
            print(f"📊 Records exported:")
            print(f"   Action Records: {len(export_data['action_records'])}")
            print(f"   Chat Messages: {len(export_data['chat_messages'])}")
            print(f"   Game Sessions: {len(export_data['game_sessions'])}")
            
        except Exception as e:
            print(f"❌ Error exporting data: {str(e)}")

async def main():
    parser = argparse.ArgumentParser(description="View stored message data")
    parser.add_argument("--type", choices=["action", "chat", "session", "all", "summary", "export"], 
                       default="all", help="Type of data to view")
    parser.add_argument("--player", help="Filter by player ID")
    parser.add_argument("--room", help="Filter by room ID")
    parser.add_argument("--limit", type=int, default=50, help="Maximum number of records to show")
    parser.add_argument("--export", help="Export data to specified filename")
    
    args = parser.parse_args()
    
    viewer = MessageViewer()
    
    if args.export:
        await viewer.export_data(args.export)
        return
    
    if args.type == "summary":
        await viewer.view_summary()
    elif args.type == "action":
        await viewer.view_action_records(args.player, args.room, args.limit)
    elif args.type == "chat":
        await viewer.view_chat_messages(args.player, args.room, args.limit)
    elif args.type == "session":
        await viewer.view_game_sessions(args.player, args.limit)
    elif args.type == "all":
        await viewer.view_summary()
        print()
        await viewer.view_action_records(args.player, args.room, args.limit)
        print()
        await viewer.view_chat_messages(args.player, args.room, args.limit)
        print()
        await viewer.view_game_sessions(args.player, args.limit)

if __name__ == "__main__":
    asyncio.run(main()) 