#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import redis
import json
from collections import defaultdict
import sys
import os
import logging
import asyncio
import argparse

# Set up basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Redis connection URL - adjust if needed
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

def rarity_to_stars(rarity):
    """Convert rarity number to star display"""
    if not rarity:
        return "☆☆☆☆"
    return "★" * rarity + "☆" * (4 - rarity)

def get_rarity_name(rarity):
    """Get rarity name from number"""
    rarity_names = {
        1: "Common",
        2: "Uncommon", 
        3: "Rare",
        4: "Legendary"
    }
    return rarity_names.get(rarity, "Unknown")

def view_items_redis(min_rarity=2, room_filter=None, item_filter=None):
    """View items from database - uses HybridDatabase since items are stored in Supabase"""
    try:
        # Items are stored in Supabase via HybridDatabase, not Redis
        # Skip Redis entirely and go straight to HybridDatabase
        logger.info("Items are stored in Supabase via HybridDatabase. Connecting to app database...")
        return asyncio.run(view_items_hybrid(min_rarity, room_filter, item_filter))
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()

# HybridDatabase (Supabase) - primary method for items
async def view_items_hybrid(min_rarity=2, room_filter=None, item_filter=None):
    try:
        # Ensure app path is importable
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
        from app.hybrid_database import HybridDatabase as Database

        db = Database()

        # Use discovered coordinates to enumerate rooms
        discovered = await db.get_discovered_coordinates()
        if not discovered:
            print("No discovered coordinates found in app database.")
            print("This could mean:")
            print("1. No rooms have been generated yet")
            print("2. Supabase configuration is missing")
            print("3. The world hasn't been initialized")
            return

        print(f"\n=== Items (Rarity {min_rarity}+) - HybridDatabase ===\n")

        items_found = 0
        items_by_rarity = defaultdict(list)
        items_by_room = defaultdict(list)

        # discovered is a dict like {"x,y": room_id}
        for coord_key, room_id in discovered.items():
            try:
                room_data = await db.get_room(room_id)
                if not room_data:
                    continue
                
                room = room_data
                room_title = room.get('title', 'Untitled Room')
                room_location = f"{room_title} ({room_id})"
                
                # Check room filter
                if room_filter and room_filter.lower() not in room_location.lower():
                    continue
                
                # Get items in this room
                item_ids = room.get('items', []) or []
                
                for item_id in item_ids:
                    try:
                        item_data = await db.get_item(item_id)
                        if not item_data:
                            continue
                        
                        item = item_data
                        
                        # Check rarity filter
                        rarity = item.get('rarity', 1)
                        if rarity < min_rarity:
                            continue
                        
                        # Check item name filter
                        if item_filter and item_filter.lower() not in item.get('name', '').lower():
                            continue
                        
                        items_found += 1
                        items_by_rarity[rarity].append(item)
                        items_by_room[room_location].append(item)
                        
                        # Display item details
                        print(f"Item: {item.get('name', 'Unnamed Item')}")
                        print(f"ID: {item.get('id', 'No ID')}")
                        print(f"Rarity: {rarity_to_stars(rarity)} ({get_rarity_name(rarity)})")
                        print(f"Location: {room_location}")
                        
                        description = item.get('description', 'No description')
                        if len(description) > 150:
                            description = description[:150] + "..."
                        print(f"Description: {description}")
                        
                        capabilities = item.get('capabilities', [])
                        if capabilities:
                            print(f"Capabilities: {', '.join(capabilities)}")
                        else:
                            print("Capabilities: None")
                        
                        properties = item.get('properties', {})
                        if properties:
                            print("Properties:")
                            for prop_key, prop_value in properties.items():
                                print(f"  {prop_key}: {prop_value}")
                        
                        print("-" * 80)
                        
                    except Exception as e:
                        logger.error(f"Error loading item {item_id}: {str(e)}")
                        continue
                        
            except Exception as e:
                logger.error(f"Error processing room {room_id}: {str(e)}")
                continue

        if items_found == 0:
            print(f"No items found with rarity {min_rarity}+")
            if room_filter:
                print(f"(filtered by room: {room_filter})")
            if item_filter:
                print(f"(filtered by item name: {item_filter})")
        else:
            # Summary statistics
            print(f"\n=== Summary ===\n")
            print(f"Total items found: {items_found}")
            
            print(f"\nBy Rarity:")
            for rarity in sorted(items_by_rarity.keys(), reverse=True):
                count = len(items_by_rarity[rarity])
                print(f"  {rarity_to_stars(rarity)} ({get_rarity_name(rarity)}): {count} items")
            
            print(f"\nBy Room:")
            for room, room_items in sorted(items_by_room.items()):
                print(f"  {room}: {len(room_items)} items")

    except Exception as e:
        logger.error(f"HybridDatabase error: {str(e)}")
        import traceback
        traceback.print_exc()

def main():
    parser = argparse.ArgumentParser(description='View items in the game database')
    parser.add_argument('--min-rarity', type=int, default=2, 
                       help='Minimum rarity to display (1-4, default: 2)')
    parser.add_argument('--room', type=str, 
                       help='Filter by room name or ID (partial match)')
    parser.add_argument('--item', type=str,
                       help='Filter by item name (partial match)')
    parser.add_argument('--rarity', type=int, choices=[1,2,3,4],
                       help='Show only specific rarity level')
    
    args = parser.parse_args()
    
    # Override min_rarity if specific rarity is requested
    min_rarity = args.rarity if args.rarity else args.min_rarity
    
    print(f"Searching for items with rarity {min_rarity}+...")
    if args.room:
        print(f"Room filter: {args.room}")
    if args.item:
        print(f"Item filter: {args.item}")
    
    view_items_redis(min_rarity, args.room, args.item)

if __name__ == "__main__":
    main()
