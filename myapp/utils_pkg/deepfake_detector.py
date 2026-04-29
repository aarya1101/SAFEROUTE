# utils/deepfake_detector.py

from transformers import AutoImageProcessor, AutoModelForImageClassification
from PIL import Image
import torch
import cv2

# ------------------------------
# ✅ Load model once globally
# ------------------------------
MODEL_NAME = "prithivMLmods/deepfake-detector-model-v1"
processor = AutoImageProcessor.from_pretrained(MODEL_NAME)
model = AutoModelForImageClassification.from_pretrained(MODEL_NAME)
labels = model.config.id2label


# ------------------------------
# ✅ Image detection function
# ------------------------------
def is_fake_image(image_path: str) -> bool:
    """
    Returns True if image is AI-generated (deepfake), else False.
    """
    image = Image.open(image_path).convert("RGB")
    inputs = processor(images=image, return_tensors="pt")
    print(f"🔍 Checking image: {image_path}")
    
    with torch.no_grad():
        outputs = model(**inputs)
        logits = outputs.logits
        predicted_class = logits.argmax(-1).item()
    

    print(f"Prediction: {labels[predicted_class]}")

    return labels[predicted_class].lower() == "fake"


# ------------------------------
# ✅ Video detection function
# ------------------------------
def is_fake_video(video_path: str, frame_skip: int = 5) -> bool:
    """
    Returns True if video contains AI-generated content.
    frame_skip: analyze every Nth frame to speed up.
    """
    cap = cv2.VideoCapture(video_path)
    frame_count = 0
    fake_detected = False

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_count % frame_skip == 0:
            # Convert OpenCV frame to PIL Image
            image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            inputs = processor(images=image, return_tensors="pt")

            with torch.no_grad():
                outputs = model(**inputs)
                logits = outputs.logits
                predicted_class = logits.argmax(-1).item()

            if labels[predicted_class].lower() == "fake":
                fake_detected = True
                break

        frame_count += 1

    cap.release()
    return fake_detected
