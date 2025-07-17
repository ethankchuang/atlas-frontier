"""
Base template classes for AI generation
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import random


class BaseTemplate(ABC):
    """Base class for all AI generation templates"""
    
    def __init__(self, name: str, category: str):
        self.name = name
        self.category = category
    
    @abstractmethod
    def generate_prompt(self, context: Dict[str, Any]) -> str:
        """Generate the prompt for the AI"""
        pass
    
    @abstractmethod
    def parse_response(self, response: str) -> Dict[str, Any]:
        """Parse the AI response into structured data"""
        pass
    
    @abstractmethod
    def validate_output(self, output: Dict[str, Any]) -> bool:
        """Validate that the output meets template requirements"""
        pass


class ItemTemplate(BaseTemplate):
    """Base class for item templates"""
    
    def __init__(self, name: str):
        super().__init__(name, "item")
    
    def generate_rarity(self) -> int:
        """Generate rarity based on weighted probabilities"""
        rand = random.random()
        if rand < 0.55:
            return 1
        elif rand < 0.85:
            return 2
        elif rand < 0.95:
            return 3
        else:
            return 4 