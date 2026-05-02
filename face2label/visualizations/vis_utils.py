import os
import numpy as np
import matplotlib.pyplot as plt
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE
from mpl_toolkits.mplot3d import Axes3D
from pathlib import Path

# Get repo root 
REPO_ROOT = Path(__file__).resolve().parents[2]

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