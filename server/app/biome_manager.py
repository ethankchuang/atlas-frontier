"""
Biome Manager - Handles biome generation and clustering logic
"""

import logging
import random
from typing import Dict, List, Set, Optional
from .ai_handler import AIHandler
from .hybrid_database import HybridDatabase as Database

logger = logging.getLogger(__name__)

class BiomeManager:
    """Manages biome generation and clustering for the world"""
    
    def __init__(self, db: Database, ai_handler: AIHandler):
        self.db = db
        self.ai_handler = ai_handler
        
    async def get_or_create_biome_for_chunk(self, chunk_id: str) -> Dict[str, str]:
        """Get existing biome for chunk or create a new one"""
        # First check if chunk already has a biome
        existing_biome = await self.db.get_chunk_biome(chunk_id)
        if existing_biome:
            return existing_biome

        # Get adjacent chunk biomes to avoid conflicts
        adjacent_biomes = await self._get_adjacent_chunk_biomes(chunk_id)

        # Get all saved biomes
        saved_biomes = await self.db.get_all_saved_biomes()
        # Remove biomes that are adjacent
        candidate_biomes = [b for b in saved_biomes if b["name"] not in adjacent_biomes]

        # Add a 'new biome' option
        options = candidate_biomes + ["__new_biome__"]
        chosen = random.choice(options)

        if chosen == "__new_biome__":
            new_biome = await self._generate_new_biome(adjacent_biomes)
            await self.db.save_biome(new_biome)
            await self.db.set_chunk_biome(chunk_id, new_biome)
            
            # Preallocate 3-star room for new biome
            await self._preallocate_three_star_room(new_biome["name"], chunk_id)
            
            logger.info(f"[BiomeManager] Created new biome '{new_biome['name']}' for chunk {chunk_id}")
            return new_biome
        else:
            await self.db.set_chunk_biome(chunk_id, chosen)
            logger.info(f"[BiomeManager] Reused existing biome '{chosen['name']}' for chunk {chunk_id}")
            return chosen
    
    async def _get_adjacent_chunk_biomes(self, chunk_id: str) -> Set[str]:
        """Get biome names from adjacent chunks"""
        # Parse chunk coordinates
        _, x_str, y_str = chunk_id.split('_')
        chunk_x, chunk_y = int(x_str), int(y_str)
        
        # Check all 4 adjacent chunks
        adjacent_chunks = [
            f"chunk_{chunk_x+1}_{chunk_y}",
            f"chunk_{chunk_x-1}_{chunk_y}",
            f"chunk_{chunk_x}_{chunk_y+1}",
            f"chunk_{chunk_x}_{chunk_y-1}"
        ]
        
        adjacent_biomes = set()
        for adj_chunk_id in adjacent_chunks:
            biome_data = await self.db.get_chunk_biome(adj_chunk_id)
            if biome_data:
                adjacent_biomes.add(biome_data["name"])
        
        return adjacent_biomes
    
    async def _find_suitable_existing_biome(self, adjacent_biomes: Set[str]) -> Optional[Dict[str, str]]:
        """Find an existing biome that's suitable to reuse (not too similar to adjacent ones)"""
        if not adjacent_biomes:
            return None
            
        # Get all saved biomes
        saved_biomes = await self.db.get_all_saved_biomes()
        
        # Find biomes that are NOT adjacent (can be safely reused)
        suitable_biomes = []
        for biome in saved_biomes:
            if biome["name"] not in adjacent_biomes:
                suitable_biomes.append(biome)
        
        if suitable_biomes:
            # Randomly select one of the suitable biomes
            return random.choice(suitable_biomes)
        
        return None
    

    
    async def _generate_new_biome(self, adjacent_biomes: Set[str]) -> Dict[str, str]:
        """Generate a new biome that's distinct from adjacent ones"""
        return await self.ai_handler.generate_biome_chunk("new_chunk", adjacent_biomes)
    
    async def _preallocate_three_star_room(self, biome_name: str, chunk_id: str) -> None:
        """Preallocate a 3-star room for a new biome"""
        # Check if this biome already has a 3-star room designated
        existing_three_star_room = await self.db.get_biome_three_star_room(biome_name)
        if existing_three_star_room:
            logger.info(f"[BiomeManager] Biome '{biome_name}' already has 3-star room: {existing_three_star_room}")
            return
        
        # Parse chunk coordinates to determine room coordinates
        _, chunk_x_str, chunk_y_str = chunk_id.split('_')
        chunk_x, chunk_y = int(chunk_x_str), int(chunk_y_str)
        
        # Calculate the center room of this chunk for the 3-star item
        # Each chunk covers about 3x3 rooms, so we'll pick the center room
        center_x = chunk_x * 3  # Approximate center
        center_y = chunk_y * 3  # Approximate center
        
        # Create a deterministic room ID for this biome's 3-star room
        room_id = f"room_{center_x}_{center_y}"
        
        # Store the 3-star room designation
        await self.db.set_biome_three_star_room(biome_name, room_id)
        logger.info(f"[BiomeManager] Preallocated 3-star room for biome '{biome_name}': {room_id} at ({center_x}, {center_y})")
    
    async def get_biome_for_coordinates(self, x: int, y: int) -> Optional[Dict[str, str]]:
        """Get biome for specific world coordinates"""
        from .game_manager import get_chunk_id
        chunk_id = get_chunk_id(x, y)
        return await self.get_or_create_biome_for_chunk(chunk_id)
    
    async def get_biome_cluster_info(self, biome_name: str) -> Dict[str, any]:
        """Get information about a biome usage"""
        # Count how many chunks use this biome
        chunk_count = 0
        for x in range(-5, 6):
            for y in range(-5, 6):
                chunk_id = f"chunk_{x}_{y}"
                biome_data = await self.db.get_chunk_biome(chunk_id)
                if biome_data and biome_data["name"] == biome_name:
                    chunk_count += 1
        
        return {
            "name": biome_name,
            "chunk_count": chunk_count,
            "estimated_room_count": chunk_count * 10,  # Rough estimate
            "is_reused": chunk_count > 1
        } 