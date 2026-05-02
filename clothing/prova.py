# ==========================================================
# Cruïlla MVP Hybrid Overlay System
# Uses MediaPipe + PNG/JPG accessories
# Input:
#   - user photo
#   - glasses.png
#   - hat.jpg
# Output:
#   final_result.png
# ==========================================================

import os
import cv2
import mediapipe as mp
import numpy as np

# ==================================================
# BASE PROJECT PATH
# ==================================================
BASE_DIR = "/export/hhome/ps2g07/code/Festival-Cruilla"

USER_IMAGE = os.path.join(BASE_DIR, "inputs", "Jordi.jpeg")

GLASSES_PATH = os.path.join(BASE_DIR, "inputs", "glasses.png")
HAT_PATH     = os.path.join(BASE_DIR, "inputs", "hat.jpg")

OUTPUT_PATH  = os.path.join(BASE_DIR, "outputs", "final_result.png")


# ==========================================================
# LOAD IMAGE WITH ALPHA SUPPORT
# ==========================================================
def load_image(path):
    img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise Exception(f"Cannot load {path}")
    return img


# ==========================================================
# CREATE ALPHA IF JPG
# ==========================================================
def ensure_alpha(img):

    if img.shape[2] == 4:
        return img

    bgr = img[:, :, :3]

    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)

    _, alpha = cv2.threshold(gray, 245, 255, cv2.THRESH_BINARY_INV)

    bgra = cv2.cvtColor(bgr, cv2.COLOR_BGR2BGRA)
    bgra[:, :, 3] = alpha

    return bgra


# ==========================================================
# OVERLAY PNG WITH TRANSPARENCY
# ==========================================================
def overlay_image(bg, overlay, x, y, scale_w, scale_h):

    overlay = cv2.resize(overlay, (scale_w, scale_h))

    h, w = overlay.shape[:2]

    if x < 0:
        overlay = overlay[:, -x:]
        w += x
        x = 0

    if y < 0:
        overlay = overlay[-y:, :]
        h += y
        y = 0

    if x + w > bg.shape[1]:
        overlay = overlay[:, :bg.shape[1]-x]
        w = overlay.shape[1]

    if y + h > bg.shape[0]:
        overlay = overlay[:bg.shape[0]-y, :]
        h = overlay.shape[0]

    if h <= 0 or w <= 0:
        return bg

    alpha = overlay[:, :, 3] / 255.0

    for c in range(3):
        bg[y:y+h, x:x+w, c] = (
            alpha * overlay[:, :, c] +
            (1 - alpha) * bg[y:y+h, x:x+w, c]
        )

    return bg


# ==========================================================
# MAIN
# ==========================================================
def main():

    img = cv2.imread(USER_IMAGE)

    if img is None:
        raise Exception("User image not found")

    h_img, w_img = img.shape[:2]

    glasses = load_image(GLASSES_PATH)
    hat = load_image(HAT_PATH)

    glasses = ensure_alpha(glasses)
    hat = ensure_alpha(hat)

    # -----------------------------------
    # Face Mesh
    # -----------------------------------
    mp_face = mp.solutions.face_mesh

    with mp_face.FaceMesh(
        static_image_mode=True,
        max_num_faces=1,
        refine_landmarks=True
    ) as face_mesh:

        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        result = face_mesh.process(rgb)

        if not result.multi_face_landmarks:
            print("No face detected")
            return

        face = result.multi_face_landmarks[0].landmark

        # ======================================
        # GLASSES LANDMARKS
        # ======================================
        left_eye = face[33]
        right_eye = face[263]

        lx = int(left_eye.x * w_img)
        ly = int(left_eye.y * h_img)

        rx = int(right_eye.x * w_img)
        ry = int(right_eye.y * h_img)

        eye_width = int(abs(rx - lx) * 1.8)
        eye_height = int(eye_width * 0.45)

        center_x = int((lx + rx) / 2)
        center_y = int((ly + ry) / 2)

        xg = center_x - eye_width // 2
        yg = center_y - eye_height // 2

        img = overlay_image(img, glasses, xg, yg, eye_width, eye_height)

        # ======================================
        # HAT LANDMARKS
        # ======================================
        forehead = face[10]
        chin = face[152]

        fx = int(forehead.x * w_img)
        fy = int(forehead.y * h_img)

        cx = int(chin.x * w_img)
        cy = int(chin.y * h_img)

        face_height = abs(cy - fy)

        hat_width = int(eye_width * 1.8)
        hat_height = int(face_height * 0.9)

        xh = fx - hat_width // 2
        yh = fy - hat_height + 20

        img = overlay_image(img, hat, xh, yh, hat_width, hat_height)

    # -----------------------------------
    # SAVE FINAL
    # -----------------------------------
    cv2.imwrite(OUTPUT_PATH, img)
    print("Saved:", OUTPUT_PATH)


if __name__ == "__main__":
    main()