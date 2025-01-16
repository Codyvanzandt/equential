import uuid
from beanie import Document
from pydantic import EmailStr, BaseModel
from typing import List, Optional, Dict
from app.config import get_settings



class Choice(BaseModel):
    user_email: EmailStr
    option_id: str 

    @classmethod
    def from_user_input(cls, user_email: str, option_id: str) -> "Choice":
        return cls(
            user_email=user_email,
            option_id=option_id
        )

class Option(BaseModel):
    id: str 
    text: str
    category: str

class ClassificationItem(BaseModel):
    item_id: str
    content: str
    options: List[Option]
    choices: List[Choice] = []

    @property
    def option_categories(self) -> Dict[str, str]:
        """Maps each option id to its category"""
        return {opt.id: opt.category for opt in self.options}

    def get_option_by_id(self, option_id: str) -> Optional[Option]:
        """Get an option by its ID"""
        for opt in self.options:
            if opt.id == option_id:
                return opt
        return None

    def get_votes_for_option(self, option_id: str) -> int:
        """Get number of votes for a specific option"""
        return len([c for c in self.choices if c.option_id == option_id])

    def get_votes_per_category(self) -> Dict[str, int]:
        """Get votes per category"""
        votes = {}
        for choice in self.choices:
            option = self.get_option_by_id(choice.option_id)
            if option:
                votes[option.category] = votes.get(option.category, 0) + 1
        return votes

    def copy(self) -> "ClassificationItem":
        """Create a copy of this item"""
        return ClassificationItem(
            item_id=self.item_id,
            content=self.content,
            options=self.options.copy(),
            choices=self.choices.copy()
        )

class Experiment(Document):
    name: str
    user_instructions: str
    items: List[ClassificationItem]
    categories: List[str] = []  # List of valid categories (e.g. ["A", "B", "C"])
    category_descriptions: Dict[str, str] = {}  # Maps categories to their descriptions

    class Settings:
        name = "experiments"

    @classmethod
    async def create_experiment(cls, name: str, instructions: str, items: List[ClassificationItem], categories: List[str], category_descriptions: Dict[str, str]) -> "Experiment":
        experiment = cls(
            name=name,
            user_instructions=instructions,
            items=items,
            categories=categories,
            category_descriptions=category_descriptions
        )
        await experiment.insert()
        return experiment

    async def record_choice(self, user_email: str, item_id: str, chosen_option_id: str) -> bool:
        # Find the item
        for item in self.items:
            if item.item_id == item_id:
                # Find the option by ID
                chosen_option = item.get_option_by_id(chosen_option_id)
                if not chosen_option:
                    return False
                    
                # Remove previous choice if it exists
                item.choices = [c for c in item.choices if c.user_email != user_email]
                # Add new choice
                item.choices.append(Choice.from_user_input(
                    user_email=user_email,
                    option_id=chosen_option.id  # Still store the text for backward compatibility
                ))
                await self.save()
                return True
        
        return False  # Item not found

    def get_unanswered_items(self, user_email: str) -> List[ClassificationItem]:
        """Get all items that haven't been answered by the user"""
        return [
            item for item in self.items
            if not any(choice.user_email == user_email for choice in item.choices)
        ]

    def get_item_results(self, item_id: str) -> Optional[Dict]:
        """Get voting results for a specific item"""
        for item in self.items:
            if item.item_id == item_id:
                total_votes = len(item.choices)
                if total_votes == 0:
                    return {
                        "item_id": item_id,
                        "content": item.content,
                        "options": item.options,
                        "option_categories": item.option_categories,
                        "total_votes": 0,
                        "votes_per_option": {option: 0 for option in item.options},
                        "votes_per_category": {cat: 0 for cat in self.categories},
                        "percentages_per_option": {option: 0 for option in item.options},
                        "percentages_per_category": {cat: 0 for cat in self.categories}
                    }
                
                # Count votes for each option
                votes_per_option = {option: 0 for option in item.options}
                for choice in item.choices:
                    votes_per_option[choice.chosen_option] += 1
                
                # Count votes for each category
                votes_per_category = {cat: 0 for cat in self.categories}
                for choice in item.choices:
                    category = item.option_categories.get(choice.chosen_option)
                    if category:
                        votes_per_category[category] += 1
                
                # Calculate percentages
                percentages_per_option = {
                    option: round((votes / total_votes * 100), 2)
                    for option, votes in votes_per_option.items()
                }
                
                percentages_per_category = {
                    cat: round((votes / total_votes * 100), 2)
                    for cat, votes in votes_per_category.items()
                }
                
                return {
                    "item_id": item_id,
                    "content": item.content,
                    "options": item.options,
                    "option_categories": item.option_categories,
                    "total_votes": total_votes,
                    "votes_per_option": votes_per_option,
                    "votes_per_category": votes_per_category,
                    "percentages_per_option": percentages_per_option,
                    "percentages_per_category": percentages_per_category
                }
        return None

class User(Document):
    email: EmailStr
    full_name: str
    access_id: str = str(uuid.uuid4())
    is_admin: bool = False
    experiment_links: dict[str, str] = {}

    class Settings:
        name = get_settings().users_collection

    @classmethod
    async def find_by_experiment_link(cls, access_id: str) -> Optional["User"]:
        """Find a user by their experiment access link"""
        users = await cls.find_all().to_list()
        for user in users:
            if access_id in user.experiment_links.values():
                return user
        return None

    @classmethod
    async def create_user(cls, email: str, full_name: str, is_admin: bool = False) -> "User":
        user = cls(
            email=email,
            full_name=full_name,
            is_admin=is_admin
        )
        await user.insert()

        # If not admin, automatically assign to all existing experiments
        if not is_admin:
            experiments = await Experiment.find_all().to_list()
            for experiment in experiments:
                await user.generate_experiment_link(str(experiment.id))
        
        return user

    async def get_experiment_for_link(self, access_id: str) -> Optional[str]:
        """Get experiment ID for a given access link"""
        return next(
            (exp_id for exp_id, link_id in self.experiment_links.items() 
             if link_id == access_id),
            None
        )

    async def generate_experiment_link(self, experiment_id: str) -> str:
        """Generate a new access link for an experiment"""
        access_id = str(uuid.uuid4())
        self.experiment_links[experiment_id] = access_id
        await self.save()
        return access_id 

    async def get_experiment_links(self) -> List[dict]:
        """Get all experiments and links for this user"""
        links = []
        for exp_id, access_id in self.experiment_links.items():
            experiment = await Experiment.get(exp_id)
            if experiment:
                # Get progress for this user
                total_items = len(experiment.items)
                answered_items = sum(
                    1 for item in experiment.items
                    if any(choice.user_email == self.email for choice in item.choices)
                )
                
                links.append({
                    "experiment_name": experiment.name,
                    "access_link": access_id,
                    "total_items": total_items,
                    "answered_items": answered_items,
                    "progress_percentage": round((answered_items / total_items * 100) if total_items > 0 else 0, 1)
                })
        return links 