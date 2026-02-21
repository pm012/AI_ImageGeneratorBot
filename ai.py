import io
import os
import time
from datetime import datetime
from io import BytesIO

from PIL import Image
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Read API keys from  .env file
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
BASE_URL = os.getenv("BASE_URL")
API_VERSION = os.getenv("API_VERSION")

# Initialize the GenAI client with custom HTTP options
options = http_options = types.HttpOptions(base_url=BASE_URL, api_version=API_VERSION)
client = genai.Client(api_key=GOOGLE_API_KEY, http_options=options)

# Models for image and video generation
IMAGE_MODEL = "gemini-2.5-flash-image"
VIDEO_MODEL = "veo-3.0-fast-generate-001"

# Settings for content safety filters
safety_settings = [
    # Alow scary content, but block the most extreme cases (e.g., gore, mutilation).
    types.SafetySetting(
        category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
        threshold=types.HarmBlockThreshold.BLOCK_NONE,
    ),
    # Any sexually explicit content will be blocked.
    types.SafetySetting(
        category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
        threshold=types.HarmBlockThreshold.BLOCK_NONE,
    ),
]


# Create an image based on a text description
def ai_create_image(prompt: str, output_path):
    config = types.GenerateContentConfig(safety_settings=safety_settings)
    response = client.models.generate_content(model=IMAGE_MODEL, contents=[prompt], config=config)
    _save_image_if_exist(response, output_path)


# Edit an existing image based on text instructions
def ai_edit_image(input_image_path: str, prompt: str, output_path):
    image = Image.open(input_image_path)

    config = types.GenerateContentConfig(safety_settings=safety_settings)
    response = client.models.generate_content(model=IMAGE_MODEL, contents=[image, prompt], config=config)
    _save_image_if_exist(response, output_path)


# Concatenate multiple images and a text prompt to create a new image
def ai_merge_image(input_image_path_list: list, prompt: str, output_path):
    data = [Image.open(image_path) for image_path in input_image_path_list]
    data.append(prompt)

    config = types.GenerateContentConfig(safety_settings=safety_settings)
    response = client.models.generate_content(model=IMAGE_MODEL, contents=data, config=config)
    _save_image_if_exist(response, output_path)


# Create a video based on a text description
def ai_video_from_text(prompt: str, out_path):
    config = types.GenerateVideosConfig(aspect_ratio="16:9", number_of_videos=1)
    op = client.models.generate_videos(model=VIDEO_MODEL, prompt=prompt, config=config)
    _save_video_if_exist(op, out_path)


# Create a video based on a text description and an input image
def ai_video_from_text_and_image(prompt: str, input_image_path: str, out_path):
    # Load the image and convert it to bytes
    im = Image.open(input_image_path)

    image_bytes_io = io.BytesIO()
    im.save(image_bytes_io, format=im.format)
    image_bytes = image_bytes_io.getvalue()

    image = types.Image(image_bytes=image_bytes, mime_type=im.format)

    config = types.GenerateVideosConfig(aspect_ratio="9:16", number_of_videos=1, )
    op = client.models.generate_videos(model=VIDEO_MODEL, prompt=prompt, image=image, config=config)

    _save_video_if_exist(op, out_path)


# Process the response from the image generation and save the image if it exists, while handling potential errors.
def _save_image_if_exist(response, output_path: str):
    # Порожня відповідь
    if not response.candidates:
        raise RuntimeError("AI was not able to generate an image based on the prompt. Please try changing the prompt.")

    cand = response.candidates[0]

    # Перевіряємо, чи не спрацював фільтр
    if cand.finish_reason and cand.finish_reason.name == "IMAGE_SAFETY":
        raise RuntimeError("The request is declined by safety filters. Please try changing the prompt.")

    if not cand.content or not cand.content.parts:
        raise RuntimeError("Answer from AI does not contain any content. Please try again.")

    # звичайна обробка
    for part in cand.content.parts:
        if part.text is not None:
            print(part.text)
        elif part.inline_data is not None:
            image = Image.open(BytesIO(part.inline_data.data))

            image = image.convert("RGB")
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            rename_with_timestamp(output_path)
            image.save(output_path, format="JPEG", quality=95)
            return True

    raise RuntimeError("Answer from AI does not contain an image.")


# Awaits for the video generation operation to complete, checks for errors, and saves the generated video if successful, while handling potential issues such as timeouts and safety filter rejections.
def _save_video_if_exist(op: types.GenerateVideosOperation, output_path: str, timeout: int = 300) -> bool:
    start = time.time()

    # Wait for the operation to complete, with a timeout to prevent infinite waiting
    while not op.done:
        if time.time() - start > timeout:
            raise TimeoutError("Awaiting for video generation timed out (exeeded 5 minutes).")
        time.sleep(3)
        op = client.operations.get(op)

    # Check if there is an answer and if it contains generated videos
    if not getattr(op, "response", None):
        raise RuntimeError("Video not generated: empty response from the model.")

    if not getattr(op.response, "generated_videos", None):
        raise RuntimeError("Video not generated: empty list of generated videos.")

    vid = op.response.generated_videos[0]

    # Check finish_reason (for example, SAFETY)
    if hasattr(vid, "finish_reason") and vid.finish_reason:
        if vid.finish_reason.name.endswith("SAFETY"):
            raise RuntimeError(f"Video was declined by safety filters: {vid.finish_reason.name}")

    # Load and save the video file
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    client.files.download(file=vid.video)
    rename_with_timestamp(output_path)
    vid.video.save(output_path)
    return True


# Create a directory for the user if it doesn't exist, ensuring that the necessary folder structure is in place for storing user-specific files such as photos and videos.
def create_user_dir(user_id):
    os.makedirs(f"resources/users/{user_id}", exist_ok=True)


# Save old photo with a timestamp before overwriting it, allowing for versioning and preventing accidental loss of previous images when new ones are generated or uploaded.
def rename_with_timestamp(file_path: str):
    if not os.path.isfile(file_path):
        return

    # Get folder, name and extension of the file
    directory, filename = os.path.split(file_path)
    name, ext = os.path.splitext(filename)

    # Format the current timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    # New filename with timestamp
    new_filename = f"{name}_{timestamp}{ext}"
    new_path = os.path.join(directory, new_filename)

    # Rename the file to the new path with timestamp
    os.rename(file_path, new_path)