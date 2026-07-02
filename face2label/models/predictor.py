import csv
import json
import os
import sys
import torch
import pandas as pd

# Allow importing auraface from the same directory regardless of CWD
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from auraface import AuraFaceExtractor, ArtistMLP


class ArtistPredictor:
    def __init__(self, model_path, labels_path, metadata_path, dataset_dir=None):
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

        # Build artist → representative image path map from dataset folder structure.
        # Folders are numbered 1-N matching CSV row order; folder 1 may be missing.
        self.image_map: dict[str, str] = {}
        if dataset_dir:
            dataset_csv = os.path.join(dataset_dir, "Fake_Artist.csv")
            if os.path.exists(dataset_csv):
                with open(dataset_csv, newline="") as f:
                    for i, row in enumerate(csv.DictReader(f)):
                        folder = os.path.join(dataset_dir, str(i + 1))
                        if not os.path.isdir(folder):
                            continue
                        imgs = sorted(
                            fn for fn in os.listdir(folder)
                            if fn.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))
                        )
                        if imgs:
                            self.image_map[row["Artist"]] = os.path.join(folder, imgs[0])

        # Load model
        self.model = ArtistMLP(num_classes=len(self.idx2label))
        self.model.load_state_dict(torch.load(model_path, map_location=self.device))
        self.model.to(self.device)
        self.model.eval()

        # Face extractor
        self.extractor = AuraFaceExtractor()

    def predict(self, image_path):
        top3 = self.predict_topk(image_path, k=1)
        if top3 is None:
            return None
        best = top3[0]
        return {
            "name":       best["name"],
            "confidence": best["confidence"],
            "genre":      self.genre_map.get(best["name"], "Unknown"),
            "tribe":      self.tribe_map.get(best["name"], "Unknown"),
        }

    def predict_topk(self, image_path, k=3):
        embedding = self.extractor.get_embedding(image_path)
        if embedding is None:
            return None

        x = torch.tensor(embedding, dtype=torch.float32).unsqueeze(0).to(self.device)

        with torch.no_grad():
            logits = self.model(x)
            probs   = torch.softmax(logits, dim=1)

        topk_probs, topk_idxs = torch.topk(probs, k=k, dim=1)

        results = []
        for prob, idx in zip(topk_probs[0], topk_idxs[0]):
            name = self.idx2label[idx.item()]
            results.append({
                "name":       name,
                "confidence": int(prob.item() * 100),
                "image":      self.image_map.get(name, ""),
            })
        return results

    def evaluate(self, val_loader, ks=(1, 3, 5)):
        """
        Compute top-k accuracy on a validation DataLoader.

        Args:
            val_loader: DataLoader yielding (embedding_tensor, label_tensor) batches.
            ks:         Tuple of k values to evaluate. Default: (1, 3, 5).

        Returns:
            dict mapping k -> accuracy (float between 0 and 1).
        """
        self.model.eval()
        correct = {k: 0 for k in ks}
        total = 0

        with torch.no_grad():
            for embeddings, labels in val_loader:
                embeddings = embeddings.to(self.device)
                labels = labels.to(self.device)

                logits = self.model(embeddings)
                probs = torch.softmax(logits, dim=1)

                max_k = max(ks)
                # topk_preds: (batch_size, max_k) — predicted indices, sorted by prob
                _, topk_preds = torch.topk(probs, k=max_k, dim=1)

                batch_size = labels.size(0)
                total += batch_size

                for k in ks:
                    # Check if the true label appears in the top-k predictions
                    top_k = topk_preds[:, :k]          # (batch_size, k)
                    labels_expanded = labels.unsqueeze(1).expand_as(top_k)
                    correct[k] += (top_k == labels_expanded).any(dim=1).sum().item()

        return {k: correct[k] / total for k in ks}

