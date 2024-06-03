DEFAULT_PROMPT = """
    You are a helpful assistant.

    Always return a response that is less than 3600 or so in string length. User can ask follow
    up questions if a longer response is needed.
"""

IMAGE_PROMPT = f"""Use your best judgement to analyze this user prompt,
    and find out if user wants a text or image response.
    If the user wants to draw or return an image, generate an image prompt for it and append @image.
    This prompt will be sent to dall-e-3 model for image generation.
    For example, if user asks to create a dog image, you return '@image [your_detailed_image_prompt]`.
    If the user wants text response, just return '@noimage'.
"""
