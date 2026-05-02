# ------------------------------------------------
# Libraries
# ------------------------------------------------
from huggingface_hub import snapshot_download
from insightface.app import FaceAnalysis

import torch
import torch.nn as nn
import torch.nn.functional as F

import numpy as np
import cv2
import os
import wandb


# ------------------------------------------------
# AuraFace model
# ------------------------------------------------

class AuraFaceExtractor():

    def __init__(self, model_dir='models/auraface', det_size=640):
        self.model_dir = model_dir
        self.det_size = det_size

        # Download model if not already downloaded
        if not os.path.exists(self.model_dir):
            snapshot_download(
                "fal/AuraFace-v1",
                local_dir=self.model_dir,
            )

        # Load and prepare detector
        self.app = FaceAnalysis(
            name="auraface",
            providers=["CUDAExecutionProvider", "CPUExecutionProvider"],
            root=".",
        )
        
        self.app.prepare(ctx_id=0, det_size=(self.det_size, self.det_size))


    def get_embedding(self, image_path):

        img = cv2.imread(image_path)

        if img is not None:

            # Get faces in the image
            faces = self.app.get(img)

            if not faces:
                return None
            
            # Select face with maximum area
            best_face = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
            # Compute face embedding
            embedding = best_face.normed_embedding

            return embedding
        
        else:
            print(f"Warning: could not read {image_path}")
            return None

# ------------------------------------------------
# MLP Classifier
# ------------------------------------------------

class ArtistMLP(nn.Module):
    def __init__(self, num_classes, hidden_dim=256, dropout=0.3):
        super().__init__()

        self.net = nn.Sequential(
            nn.Linear(512, hidden_dim),
            nn.BatchNorm1d(hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, hidden_dim//2),
            nn.BatchNorm1d(hidden_dim//2),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim//2, num_classes)
        )

    def forward(self, x):
        return self.net(x)

# ------------------------------------------------
# Train and Eval functions
# ------------------------------------------------

def train(train_loader, val_loader, num_classes, epochs=100, lr=1e-3, device=None):

    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"

    # Initialize wandb run
    wandb.init(
        project="festival-cruilla",
        config={"num_classes": num_classes, "epochs": epochs, "lr": lr},
    )

    # Create model, optimizer, loss
    model = ArtistMLP(num_classes=num_classes).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    criterion = nn.CrossEntropyLoss()

    # Training loop
    for epoch in range(1, epochs + 1):

        # --- Train phase ---
        model.train()
        train_loss, train_correct, train_total = 0.0, 0, 0

        for embed, lbl in train_loader:
            embed, lbl = embed.to(device), lbl.to(device)
            logits = model(embed)
            loss = criterion(logits, lbl)

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            train_loss += loss.item() * embed.size(0)
            train_correct += (logits.argmax(dim=1) == lbl).sum().item()
            train_total += embed.size(0)

        # --- Validation phase ---
        model.eval()
        val_loss, val_correct, val_total = 0.0, 0, 0

        with torch.no_grad():
            for embed, lbl in val_loader:
                embed, lbl = embed.to(device), lbl.to(device)
                logits = model(embed)
                loss = criterion(logits, lbl)

                val_loss += loss.item() * embed.size(0)
                val_correct += (logits.argmax(dim=1) == lbl).sum().item()
                val_total += embed.size(0)

        # --- Log metrics ---
        train_loss_avg = train_loss / train_total
        train_acc = train_correct / train_total
        val_loss_avg = val_loss / val_total
        val_acc = val_correct / val_total

        wandb.log({
            "epoch": epoch,
            "train/loss": train_loss_avg,
            "train/accuracy": train_acc,
            "val/loss": val_loss_avg,
            "val/accuracy": val_acc,
        })

        print(
            f"Epoch {epoch:3d}/{epochs}  "
            f"train_loss={train_loss_avg:.4f}  train_acc={train_acc:.2%}  "
            f"val_loss={val_loss_avg:.4f}  val_acc={val_acc:.2%}"
        )

    wandb.finish()
    return model

