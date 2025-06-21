import os

from dotenv import load_dotenv

# Load environment variables
load_dotenv()


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME")
TEAM_MEMBERS = ["calendar", "search", "sharing", "travel_planner"]
