import os
import numpy as np
import matplotlib.pyplot as plt
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE
from mpl_toolkits.mplot3d import Axes3D
from pathlib import Path
from PIL import Image
import random
import torch

# Get repo root 
REPO_ROOT = Path(__file__).resolve().parents[2]


# -----------------------------------------------------
# FEATURE SPACE VISUALIZATION
# -----------------------------------------------------

def visualize_embeddings(embeddings, labels, method="tsne"):
    X = np.array(embeddings)
    y = np.array(labels)

    # --- Dimensionality reduction ---
    if method == "pca":
        reducer = PCA(n_components=3)
        X_reduced = reducer.fit_transform(X)

    elif method == "tsne":
        reducer = TSNE(n_components=3, perplexity=30, random_state=42)
        X_reduced = reducer.fit_transform(X)

    else:
        raise ValueError("method must be 'pca' or 'tsne'")

    # --- 3D Plot ---
    fig = plt.figure(figsize=(10, 8))
    ax = fig.add_subplot(111, projection='3d')

    ax.scatter(
        X_reduced[:, 0],
        X_reduced[:, 1],
        X_reduced[:, 2],
        c=y,
        cmap="tab20",
        s=20,
        alpha=0.7
    )

    ax.set_title(f"AuraFace Embedding Space Visualization ({method.upper()})")
    ax.set_xlabel("Dim 1")
    ax.set_ylabel("Dim 2")
    ax.set_zlabel("Dim 3")

    plt.tight_layout()

    # --- Save figure ---
    output_dir = REPO_ROOT / "outputs"
    save_path = output_dir / f"embedding_space_{method}.jpg"
    plt.savefig(save_path, dpi=300, bbox_inches="tight")

    print(f"Saved to: {save_path}")

    plt.close(fig)  

# -----------------------------------------------------
# MODEL PREDICTIONS VISUALIZATION
# -----------------------------------------------------

def visualize_predictions(model, extractor, samples, label2idx, device, n=5, save_path=True):
    """
    Visualize n random samples with their true and predicted artist labels.
    """

    idx2label = {v: k for k, v in label2idx.items()}
    model.eval()

    # Pick n random (image_path, true_label) pairs
    flat_samples = [(path, artist) for image_paths, artist in samples for path in image_paths]
    chosen = random.sample(flat_samples, n)

    fig, axes = plt.subplots(1, n, figsize=(4 * n, 5))
    if n == 1:
        axes = [axes]

    for ax, (path, true_artist) in zip(axes, chosen):
        # Get image for display
        img = Image.open(path).convert("RGB")

        # Get embedding and predict
        embedding = extractor.get_embedding(path)
        if embedding is None:
            embedding = np.zeros(512, dtype=np.float32)

        with torch.no_grad():
            tensor = torch.tensor(embedding, dtype=torch.float32).unsqueeze(0).to(device)
            logits = model(tensor)
            pred_idx = logits.argmax(dim=1).item()
            confidence = torch.softmax(logits, dim=1).max().item()

        pred_artist = idx2label[pred_idx]
        correct = (pred_artist == true_artist)

        ax.imshow(img)
        ax.axis("off")
        ax.set_title(
            f"GT:   {true_artist}\nPred: {pred_artist} ({confidence:.0%})",
            fontsize=9,
            color="green" if correct else "red",
            pad=6
        )

    plt.suptitle("Sample Predictions", fontsize=13, fontweight="bold")
    plt.tight_layout()

    if save_path:
        output_dir = REPO_ROOT / "outputs"
        save_dir = output_dir / "predictions.png"
        plt.savefig(save_dir, dpi=300, bbox_inches="tight")

# -----------------------------------------------------
# VISUALIZE TOP 3 PREDICTED ARTISTS
# -----------------------------------------------------

def predict_top3(image_path, model, extractor, idx2label, label2idx, dataset, device):
    model.eval()

    embedding = extractor.get_embedding(image_path)
    if embedding is None:
        print("No face detected in image.")
        return

    with torch.no_grad():
        tensor = torch.tensor(embedding, dtype=torch.float32).unsqueeze(0).to(device)
        probs = torch.softmax(model(tensor), dim=1).squeeze().cpu()

    top3_probs, top3_idxs = torch.topk(probs, 3)
    top3_artists = [idx2label[i.item()] for i in top3_idxs]
    top3_probs = top3_probs.numpy()

    # Get one representative image per top3 artist from the dataset
    artist2paths = {artist: paths for paths, artist in dataset.samples}

    fig, axes = plt.subplots(1, 4, figsize=(16, 4))

    # Input image
    axes[0].imshow(Image.open(image_path).convert("RGB"))
    axes[0].set_title("Input", fontsize=11, fontweight="bold")
    axes[0].axis("off")

    # Top 3 artist images
    for i, (artist, prob) in enumerate(zip(top3_artists, top3_probs)):
        rep_image = Image.open(artist2paths[artist][0]).convert("RGB")
        axes[i + 1].imshow(rep_image)
        axes[i + 1].set_title(f"{artist}\n{prob:.1%}", fontsize=10,
                               color="green" if i == 0 else "black")
        axes[i + 1].axis("off")

    plt.suptitle("Top 3 Most Similar Artists", fontweight="bold")

    output_dir = REPO_ROOT / "outputs"
    save_dir = output_dir / "top3_predictions.png"
    plt.savefig(save_dir, dpi=300, bbox_inches="tight")