from pathlib import Path
import argparse
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

import librosa
import librosa.feature
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA


def extract_features(path: Path):
    y, sr = librosa.load(path, sr=None, mono=True)

    duration = librosa.get_duration(y=y, sr=sr)
    rms = librosa.feature.rms(y=y).mean()
    loudness_db = 20 * np.log10(rms + 1e-9)

    zcr = librosa.feature.zero_crossing_rate(y).mean()
    centroid = librosa.feature.spectral_centroid(y=y, sr=sr).mean()
    bandwidth = librosa.feature.spectral_bandwidth(y=y, sr=sr).mean()
    rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr).mean()

    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    tempo = float(np.asarray(tempo).squeeze())

    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
    mfcc_mean = mfcc.mean(axis=1)
    mfcc_std = mfcc.std(axis=1)

    chroma = librosa.feature.chroma_stft(y=y, sr=sr)
    chroma_mean = chroma.mean(axis=1)

    features = {
        "file": path.name,
        "duration": duration,
        "loudness_db": loudness_db,
        "rms": rms,
        "zero_crossing_rate": zcr,
        "spectral_centroid": centroid,
        "spectral_bandwidth": bandwidth,
        "spectral_rolloff": rolloff,
        "tempo": tempo,
    }

    for i, value in enumerate(mfcc_mean, start=1):
        features[f"mfcc{i}_mean"] = value

    for i, value in enumerate(mfcc_std, start=1):
        features[f"mfcc{i}_std"] = value

    for i, value in enumerate(chroma_mean, start=1):
        features[f"chroma{i}_mean"] = value

    return features


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "files",
        nargs="*",
        help="Audio files. If empty, uses outputs/music/metrics/*.wav",
    )
    parser.add_argument(
        "--audio_dir",
        default="outputs/music/metrics",
        help="Default folder if no files are passed",
    )
    parser.add_argument(
        "--out",
        default="audio_feature_report",
        help="Output prefix for CSV and plots",
    )

    args = parser.parse_args()

    if args.files:
        paths = [Path(p) for p in args.files]
    else:
        paths = sorted(Path(args.audio_dir).glob("*.wav"))

    if len(paths) < 2:
        raise SystemExit(f"Need at least 2 wav files. Found {len(paths)}.")

    print(f"[Analysis] Found {len(paths)} files")

    rows = []
    for path in paths:
        print(f"[Analysis] Processing {path}")
        rows.append(extract_features(path))

    df = pd.DataFrame(rows)
    csv_path = f"{args.out}.csv"
    df.to_csv(csv_path, index=False)
    print(f"[Analysis] Saved table -> {csv_path}")

    feature_cols = [c for c in df.columns if c != "file"]
    X = df[feature_cols].values
    X_scaled = StandardScaler().fit_transform(X)

    pca = PCA(n_components=2)
    coords = pca.fit_transform(X_scaled)

    df["pca1"] = coords[:, 0]
    df["pca2"] = coords[:, 1]

    # Plot 1: PCA / latent space
    plt.figure(figsize=(9, 7))
    plt.scatter(df["pca1"], df["pca2"], s=90)

    for _, row in df.iterrows():
        label = Path(row["file"]).stem[:18]
        plt.text(row["pca1"], row["pca2"], label, fontsize=8)

    plt.xlabel(f"PCA 1 ({pca.explained_variance_ratio_[0] * 100:.1f}% variance)")
    plt.ylabel(f"PCA 2 ({pca.explained_variance_ratio_[1] * 100:.1f}% variance)")
    plt.title("Audio feature latent space / PCA")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    pca_path = f"{args.out}_pca.png"
    plt.savefig(pca_path, dpi=160)
    plt.close()
    print(f"[Analysis] Saved PCA plot -> {pca_path}")

    # Plot 2: loudness vs spectral centroid
    plt.figure(figsize=(8, 6))
    plt.scatter(df["spectral_centroid"], df["loudness_db"], s=90)

    for _, row in df.iterrows():
        label = Path(row["file"]).stem[:14]
        plt.text(row["spectral_centroid"], row["loudness_db"], label, fontsize=8)

    plt.xlabel("Spectral centroid")
    plt.ylabel("Loudness / RMS dB")
    plt.title("Brightness vs loudness")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    scatter_path = f"{args.out}_brightness_loudness.png"
    plt.savefig(scatter_path, dpi=160)
    plt.close()
    print(f"[Analysis] Saved scatter plot -> {scatter_path}")

    # Plot 3: main descriptor bar plots
    summary_features = [
        "duration",
        "loudness_db",
        "tempo",
        "spectral_centroid",
        "spectral_bandwidth",
        "zero_crossing_rate",
    ]

    for col in summary_features:
        plt.figure(figsize=(10, 5))
        labels = [Path(f).stem[:16] for f in df["file"]]
        plt.bar(labels, df[col])
        plt.xticks(rotation=45, ha="right")
        plt.ylabel(col)
        plt.title(f"{col} per audio")
        plt.tight_layout()
        path = f"{args.out}_{col}.png"
        plt.savefig(path, dpi=160)
        plt.close()
        print(f"[Analysis] Saved {col} plot -> {path}")

    print("\nMain metrics:")
    print(df[["file", "duration", "loudness_db", "tempo", "spectral_centroid", "spectral_bandwidth"]])


if __name__ == "__main__":
    main()