DEFAULT_PROMPT = """
    You are a helpful assistant.
"""

IMAGE_PROMPT = f"""Use your best judgement to analyze this user prompt,
    and find out if user wants a text or image response.
    If the user wants to draw or return an image, generate an image prompt for it and append @image.
    This prompt will be sent to dall-e-3 model for image generation.
    For example, if user asks to create a dog image, you return '@image [your_detailed_image_prompt]`.
    If the user wants text response, just return '@noimage'.
"""
