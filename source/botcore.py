# models
# def text_davinci_response(text: str) -> str:
#     response = openai.Completion.create(
#         engine="text-davinci-003",
#         prompt=text,
#         max_tokens=2048,
#         n=1,
#         stop=None,
#         temperature=0.5,
#     )
#     return response.choices[0].text.strip()