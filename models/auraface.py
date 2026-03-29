from huggingface_hub import snapshot_download
from insightface.app import FaceAnalysis
import numpy as np
import cv2

snapshot_download(
    "fal/AuraFace-v1",
    local_dir="models/auraface",
)

face_app = FaceAnalysis(
    name="auraface",
    providers=["CUDAExecutionProvider", "CPUExecutionProvider"],
    root=".",
)
face_app.prepare(ctx_id=0, det_size=(640, 640))

input_image = cv2.imread("mushka.png")

faces = face_app.get(input_image)
embedding = faces[0].normed_embedding
print(len(embedding))