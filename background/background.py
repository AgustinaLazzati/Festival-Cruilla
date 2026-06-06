import random
import os
from rembg import remove
from PIL import Image

# ==============================================================================
# MODEL USED the rembg library uses the U-2-Net (u2net) model.
# ==============================================================================

# Setup your file names here
BACKGROUNDS = ['background1.png', 'background2.png', 'background3.png', 'background4.png']
INPUT_IMAGE_PATH = 'image.png' # The picture you already took
OUTPUT_IMAGE_PATH = 'final_result.jpg'

def process_image(input_path):
    """Loads an image, removes the background, and applies a random new one."""
    
    # Check if the input image exists
    if not os.path.exists(input_path):
        print(f"Error: Could not find '{input_path}'. Make sure it's in the same folder.")
        return
        
    print(f"Loading '{input_path}'...")
    person_img = Image.open(input_path)
    
    print("Removing background...")
    # 1. Remove the background (returns an RGBA image with transparent background)
    subject_no_bg = remove(person_img)

    # 2. Pick a random background
    chosen_bg_path = random.choice(BACKGROUNDS)
    print(f"Applying random background: {chosen_bg_path}")

    if not os.path.exists(chosen_bg_path):
        print(f"Error: Could not find '{chosen_bg_path}'. Make sure your backgrounds are in the folder.")
        return

    # 3. Open the background and ensure it has an alpha channel
    bg_img = Image.open(chosen_bg_path).convert("RGBA")

    # 4. Resize the background to match your input photo's resolution
    bg_img = bg_img.resize(subject_no_bg.size)

    # 5. Paste the subject onto the background
    # The third argument uses the subject's transparency (alpha channel) as a mask
    bg_img.paste(subject_no_bg, (0, 0), subject_no_bg)

    # 6. Save and show the final result
    final_image = bg_img.convert("RGB") # Convert back to RGB to save as a standard JPG
    final_image.save(OUTPUT_IMAGE_PATH)
    print(f"Success! Image saved as '{OUTPUT_IMAGE_PATH}'.")
    
    # Opens the image using your computer's default image viewer
    final_image.show()

if __name__ == "__main__":
    process_image(INPUT_IMAGE_PATH)