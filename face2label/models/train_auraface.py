import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

import torch
import numpy as np
from sklearn.model_selection import train_test_split
from auraface import AuraFaceExtractor
from torch.utils.data import DataLoader, TensorDataset

from auraface import train
from datasets.fake_artists_dataset import FakeArtistsDataset
from visualizations.vis_utils import *


# ------------------------------------------------
# Config
# ------------------------------------------------
ROOT_DIR   = "/hhome/ps2g07/code/data/Fake_Artists"
EPOCHS     = 16
LR         = 1e-3
VAL_SPLIT  = 0.2
HIDDEN_DIM = 256
DROPOUT    = 0.3

# ------------------------------------------------
# Helper function to get the embeddings
# ------------------------------------------------

def get_embeddings_list(dataset, extractor, label2idx):

    embeddings = []
    for image_paths, artist_name in dataset.samples:
        idx = label2idx[artist_name]

        for path in image_paths:
            embedding = extractor.get_embedding(path)

            if embedding is None:
                embedding = np.zeros(512, dtype=np.float32)

            embeddings.append((embedding, idx))
        
    return embeddings

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

    # --- Extract embeddings ---
    extractor = AuraFaceExtractor()
    full_dataset = get_embeddings_list(base_dataset, extractor, label2idx)
    print(f"Total images: {len(full_dataset)}")

    # --- Train/val split ---
    embeddings, labels = zip(*full_dataset)
    print("Total Embeddings:", len(embeddings))

    # Visualize model embedding space
    visualize_embeddings(embeddings, labels, method="pca")

    X_train, X_val, y_train, y_val = train_test_split(embeddings, labels, test_size=0.2)

    train_dataset = TensorDataset(
        torch.tensor(np.array(X_train), dtype=torch.float32),
        torch.tensor(y_train, dtype=torch.long)
    )
    val_dataset = TensorDataset(
        torch.tensor(np.array(X_val), dtype=torch.float32),
        torch.tensor(y_val, dtype=torch.long)
    )

    train_loader = DataLoader(train_dataset, batch_size=16, shuffle=True)
    val_loader   = DataLoader(val_dataset,   batch_size=16, shuffle=False)
    print(f"Train: {len(X_train)} images | Val: {len(X_val)} images")

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