import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

import torch
import numpy as np
from torch.utils.data import DataLoader, random_split
from auraface import AuraFaceExtractor, ArtistMLP
import wandb
from auraface import train
from datasets.fake_artists_dataset import FakeArtistsDataset



# ------------------------------------------------
# Config
# ------------------------------------------------
ROOT_DIR   = "/hhome/ps2g07/code/data/Fake_Artists"
EPOCHS     = 100
LR         = 1e-3
VAL_SPLIT  = 0.2
HIDDEN_DIM = 256
DROPOUT    = 0.3


# ------------------------------------------------
# Embedding Dataset wrapper
# ------------------------------------------------
class EmbeddingDataset(torch.utils.data.Dataset):
    """
    Wraps FakeArtistsDataset and extracts AuraFace embeddings on-the-fly.
    Returns (embedding_tensor, label_idx) pairs.
    """
    def __init__(self, fake_artists_dataset, extractor, label2idx):
        self.dataset   = fake_artists_dataset
        self.extractor = extractor
        self.label2idx = label2idx

        # Flatten: one entry per image (not per artist)
        # Each item: (image_path, label_idx)
        self.items = []
        for image_paths, artist_name in fake_artists_dataset.samples:
            idx = label2idx[artist_name]
            for path in image_paths:
                self.items.append((path, idx))

    def __len__(self):
        return len(self.items)

    def __getitem__(self, idx):
        path, label_idx = self.items[idx]
        embedding = self.extractor.get_embedding(path)

        if embedding is None:
            # Return a zero vector if no face detected
            embedding = np.zeros(512, dtype=np.float32)

        return torch.tensor(embedding, dtype=torch.float32), label_idx


# ------------------------------------------------
# Main
# ------------------------------------------------
def main():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Using device: {device}")

    # --- Load dataset ---
    base_dataset = FakeArtistsDataset(root_dir=ROOT_DIR, transform=None)

    # Build label: index mapping from artist names
    artist_names = [name for _, name in base_dataset.samples]
    unique_artists = sorted(set(artist_names))
    label2idx = {name: i for i, name in enumerate(unique_artists)}
    num_classes = len(unique_artists)
    print(f"Artists: {num_classes}")

    # --- Extract embeddings on-the-fly ---
    extractor = AuraFaceExtractor()
    full_dataset = EmbeddingDataset(base_dataset, extractor, label2idx)
    print(f"Total images: {len(full_dataset)}")

    # --- Train/val split ---
    val_size   = int(len(full_dataset) * VAL_SPLIT)
    train_size = len(full_dataset) - val_size
    train_dataset, val_dataset = random_split(full_dataset, [train_size, val_size])

    train_loader = DataLoader(train_dataset, batch_size=16, shuffle=True)
    val_loader   = DataLoader(val_dataset,   batch_size=16, shuffle=False)
    print(f"Train: {train_size} images | Val: {val_size} images")

    # --- Train ---
    model = train(
        train_loader=train_loader,
        val_loader=val_loader,
        num_classes=num_classes,
        epochs=EPOCHS,
        lr=LR,
        device=device,
    )

    return model


if __name__ == "__main__":
    main()