from typing import Dict, Any

# Target feature ranges/centers tuned for accuracy.
# We’ll send these as target_* to Spotify’s recommendations
# and then do a secondary score-based sort.
VIBE_FEATURES: Dict[str, Dict[str, Any]] = {
    "mellow": {
        "target_energy": 0.25,
        "target_valence": 0.45,
        "target_acousticness": 0.45,
        "min_tempo": 60, "max_tempo": 100,
        "target_danceability": 0.45
    },
    "energetic": {
        "target_energy": 0.85,
        "target_valence": 0.7,
        "target_acousticness": 0.1,
        "min_tempo": 110, "max_tempo": 160,
        "target_danceability": 0.75
    },
    "sad": {
        "target_energy": 0.3,
        "target_valence": 0.2,
        "target_acousticness": 0.35,
        "min_tempo": 60, "max_tempo": 95,
        "target_danceability": 0.35
    },
    "happy": {
        "target_energy": 0.7,
        "target_valence": 0.85,
        "target_acousticness": 0.15,
        "min_tempo": 100, "max_tempo": 150,
        "target_danceability": 0.7
    },
    "focus": {
        "target_energy": 0.35,
        "target_valence": 0.35,
        "target_acousticness": 0.6,
        "min_tempo": 70, "max_tempo": 120,
        "target_danceability": 0.45
    },
    "epic": {
        "target_energy": 0.9,
        "target_valence": 0.55,
        "target_acousticness": 0.05,
        "min_tempo": 120, "max_tempo": 180,
        "target_danceability": 0.6
    },
}

# Optional genre nudges (seed genres)
VIBE_SEED_GENRES = {
    "mellow": ["chill", "acoustic", "ambient"],
    "energetic": ["edm", "dance", "house", "rock"],
    "sad": ["sad", "singer-songwriter", "piano"],
    "happy": ["pop", "funk", "dance-pop"],
    "focus": ["lo-fi", "ambient", "classical"],
    "epic": ["orchestral", "trailerr", "power-metal", "electro"]
}

def instrumental_filter_threshold(lyrical: bool):
    # If user wants non-lyrical: push instrumentalness high.
    # If lyrical: keep instrumentalness modest.
    return (0.2, 0.5) if lyrical else (0.8, 1.0)  # (min,max) desired band
