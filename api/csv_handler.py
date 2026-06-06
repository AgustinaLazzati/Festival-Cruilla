"""
Module to save user answers to Users_Answers.csv
"""

import pandas as pd
import uuid
from pathlib import Path
from datetime import datetime

CSV_PATH = Path(__file__).parent.parent / "data" / "Users_Answers.csv"


def load_existing_data():
    """Load existing Users_Answers.csv"""
    try:
        if CSV_PATH.exists():
            return pd.read_csv(CSV_PATH)
        else:
            return pd.DataFrame()
    except Exception as e:
        print(f"Error loading CSV: {e}")
        return pd.DataFrame()


def save_user_response(mood: str, instrument: str, era: str):
    """
    Save user responses to CSV.
    Creates a new row with user answers.
    Other columns are commented out (set as empty) until we have the full model data.
    
    Args:
        mood: 'happy', 'sad', or 'chill'
        instrument: 'guitar', 'piano', 'trumpet', or 'drums'
        era: 'medieval', '90s', 'futuristic', or 'actual'
    """
    try:
        df = load_existing_data()
        
        # Create new row with user responses
        session_id = str(uuid.uuid4())[:8]
        timestamp = datetime.now().isoformat()
        
        new_row = {
            "SessionID": session_id,
            "Timestamp": timestamp,
            "Mood": mood,                    # 👈 User input
            "Instrument": instrument,        # 👈 User input
            "Era": era,                      # 👈 User input
            # Following columns are placeholders (will be filled by matching models)
            "Artist": None,                  # Will be filled by facial recognition
            "Real_Artist": None,             # Will be filled by matching
            "Genre": None,                   # Will be filled by matching
            "Energy": None,                  # Will be filled by matching
            "Main_Instrument": None,         # Will be filled by matching
            "Matched_Confidence": None,      # Will be filled by facial recognition
            "Generated_Music_Path": None,    # Will be filled by music generation
            "Tribe": None                    # Will be filled after matching
        }
        
        # Append new row
        new_df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        
        # Save to CSV
        new_df.to_csv(CSV_PATH, index=False)
        
        print(f"✅ Saved response: {session_id}")
        return session_id
        
    except Exception as e:
        print(f"❌ Error saving to CSV: {e}")
        return None


def get_user_session(session_id: str):
    """Retrieve user session data by ID"""
    try:
        df = load_existing_data()
        return df[df["SessionID"] == session_id].to_dict("records")[0]
    except Exception as e:
        print(f"Error retrieving session: {e}")
        return None


if __name__ == "__main__":
    # Test
    session_id = save_user_response(
        mood="happy",
        instrument="guitar",
        era="futuristic"
    )
    print(f"Session saved: {session_id}")
