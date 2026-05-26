import json
import os
import sys
import torch
import pandas as pd

# Allow importing auraface from the same directory regardless of CWD
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from auraface import AuraFaceExtractor, ArtistMLP


class ArtistPredictor:
    def __init__(self, model_path, labels_path, metadata_path):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        # Load label mapping
        with open(labels_path, "r") as f:
            raw = json.load(f)
            self.idx2label = {int(k): v for k, v in raw.items()}

        # Load metadata
        df = pd.read_csv(metadata_path)

        self.genre_map = {
            row["Artist"]: row["Genre"]
            for _, row in df.iterrows()
        }

        self.tribe_map = {
            row["Artist"]: row["Tribe"]
            for _, row in df.iterrows()
            if "Tribe" in df.columns
        }

        # Load model
        self.model = ArtistMLP(num_classes=len(self.idx2label))
        self.model.load_state_dict(torch.load(model_path, map_location=self.device))
        self.model.to(self.device)
        self.model.eval()

        # Face extractor
        self.extractor = AuraFaceExtractor()

    def predict(self, image_path):
        embedding = self.extractor.get_embedding(image_path)

        if embedding is None:
            return None

        x = torch.tensor(embedding, dtype=torch.float32).unsqueeze(0).to(self.device)

        with torch.no_grad():
            logits = self.model(x)
            probs = torch.softmax(logits, dim=1)

        conf, idx = torch.max(probs, dim=1)
        idx = idx.item()

        artist_name = self.idx2label[idx]

        return {
            "name": artist_name,
            "confidence": int(conf.item() * 100),
            "genre": self.genre_map.get(artist_name, "Unknown"),
            "tribe": self.tribe_map.get(artist_name, "Unknown"),
        }